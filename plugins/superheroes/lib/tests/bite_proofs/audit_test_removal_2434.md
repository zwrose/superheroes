# Bite-proof record — a fix that only removes worthless test lines clears its audit on a `worthless-test-removed` answer (#2434)

Detector file: `plugins/superheroes/lib/tests/test_audit_test_removal_2434.py`, unedited between each red and its green. Every entry is a targeted, reversible Edit-tool edit to one production file (`plugins/superheroes/lib/audits.py` for G1-G8, G13-G15, G17, G18, G20, G24-G27 and G29, `plugins/superheroes/lib/round_driver.py` for G9-G12, G16, G19, G21-G23 and G28), restored by the inverse edit (no `git checkout`, `restore`, `reset` or `stash`). Runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest '<exact node id>' -q -n 0 --tb=short`, one test node each, output captured whole, followed by the `exit=` line the command printed. Each `old_string` occurred exactly once (the Edit tool refuses a non-unique match). No secrets, tokens, private URLs or PII appear in any capture. One redaction: the absolute path of the build worktree, which prefixes the file paths in the tracebacks, is written `<worktree>`; nothing else was redacted.

The twenty-nine guarded elements (declared by the order of WO-F, #2434: G8, G14 and G18 re-captured or extended, G24-G28 new; G29 added by WO-H, after vet 889): G1 the clear arm, G2-G8 the refusals C1-C7 (G8 now the per-line C7), G9 the `added` detection, G10 the unreadable detection, G11 `--no-textconv`, G12 the explicit endpoint, G13 the refusal C8 (an unsupported language), G14 the refusal C9 (now per line: a removed line whose innermost test span opens on an uncited line), G15 the refusal C10 (a citation that is not exactly fresh), G16 `--inter-hunk-context=0`, G17 the Python test-opening reader, G18 the JavaScript/TypeScript test-opening reader, G19 the unreadable-base-blob form, G20 the sibling freshness gate (a sibling lends its cited lines only when its driver-built `citationFresh` is exactly True), G21 the no-repository / no-removal-head branch of `_citation_freshness`, G22 its no-cited-file / unresolved-head branch, G23 its changed-file branch, G24 the span end rule of `audits.test_spans`, G25 the innermost-span choice in C9, G26 the decorator start rule of `audits.test_spans`, G27 the `_removal_files` validation of `testSpans` and `blankLines`, G28 `_fixer_removal`'s `testSpans` and `blankLines`, G29 the modifier match of `audits.JS_TEST_OPENING` (a member call on an opening name is an opening). The new answer on `right` or `brokeNothing` (a shape fault) and on a `not-discharged` ruling (no clearing, no listing) are plain tests, not guarded elements.

**WO-F of #2434 (the span tie, after vet 888).** C7 and C9 became per removed line, tied to the test spans the driver reads (`testSpans`, `blankLines`), so G8 and G14 were captured again on the new branches (their earlier entries are replaced) and G24-G28 were added. Every red and green of G8, G14 and G24-G28 below was run on the tree of this leg, on one test node each, the detector unedited between its red and its green except where an entry says otherwise (G24's real-text node and G26's node each lost one precondition assertion on the span the reader returns before their red was captured, so the red lands on the clearance and not on a precondition). The restore receipts of those entries were read back by the Grep or Read tool right after each restore. The other entries (G1-G7, G9-G13, G15-G23) were not captured again in this leg; their detectors are unchanged except that `_row` now carries `testSpans` and `blankLines` and the C2 parametrization has more cases, and the final scoped run is green on them.

G1-G12 were captured again in the fix leg of vet 886: the fixtures gained `testOpenings` and `citationFresh`, which moved the detectors' line numbers and the production files' line numbers, so every earlier red and green was re-run and replaced. The restore receipts of G1-G12 were read back by one Grep after the last of them was restored (every restored line appears in it); those of G13-G23 were read back right after each restore. G20-G23 were captured in WO-D of #2434: the fixtures' siblings gained `citationFresh`, and the freshness branches of `_citation_freshness` got their neutralizations; G1-G19 were not captured again in that leg. One slip in G21's restore: the first inverse edit dropped the space after `raised =` (`raised =_resolve_commit_sha(`, still valid Python and the same behaviour); a `git diff` after G23 showed it and a further inverse edit put the space back, so the G21 green, the G22 red and green and the G23 red and green all ran with that one-space difference in the tree, and the final scoped run runs on the fully restored file.

**Grouping** (the grouping rule of `rubric/bite-proof.md`: a class is a distinct failure mode, named by its representative, and every grouped input keeps its own test case). Each condition element proves one representative input; the inputs it groups run in the same test function or parametrization and are not neutralized one by one:

- G3 (C2, the removal record is readable and well formed): representative a range with `start > end` (`[start-after-end]`); it groups an absent record, `None`, an `unreadable` record, an empty or non-list `files`, a range with start `0`, a bool, a string or a float, a range of the wrong length or not a list, a blank or non-string path, an `added` that is not a bool, a row that is not a dict, a path named twice, and a `testOpenings` that is absent, not a list, or holds a bool, `0`, a negative, a string, a float or a list (the ten `openings-*` cases; the `_removal_files` branch that rejects them has its own `# axis:` line and is not neutralized one by one).
- G5 (C4, the fix added nothing): representative `added: True`; it groups a file with no removed range (`test_c4_a_file_with_no_removed_range_refuses`).
- G6 (C5, the target is a worthless-test finding): representative a wrong dimension (`[wrong-dimension]`); it groups no or differently cased dimension, an unknown or near-miss taxonomy, a `None` or non-string taxonomy, and a blank, missing or non-string body.
- G7 (C6, one of the target's own cited lines lies in a removed range): representative a `line` outside every removed range; it groups a `line` that is `None`, a bool, a string or a float (`test_c6_a_line_that_is_not_a_plain_integer_cites_nothing`) and a sibling's line that does not supply the target's own tie (`test_c6_a_siblings_line_does_not_tie_a_removal_the_target_does_not_cite`). With C6 neutralized the first case falls through to C7 and still reds the detector, as the capture shows; the sibling case is the one whose result C6 alone decides.
- G8 (C7, a removed line outside every test span, neither cited nor blank, needs a cited line in its range): representative an extra range tied to nothing; it groups a sibling that fails C5 (`test_c7_a_sibling_that_is_not_a_worthless_test_finding_ties_nothing`, five cases), a sibling that is not a dict, a file with no reader (every line lies in no span; `test_c7_a_file_with_no_reader_refuses_its_uncited_lines_as_c7_before_c8`), and a range of which only some lines are blank. (`test_c7_an_uncited_stretch_with_no_test_opening_still_refuses` was a duplicate of the representative and is deleted.)
- G10 (the unreadable forms of `_fixer_removal`): representative a real binary file; it groups a two-path header, a git-quoted header, a `Binary files` line, a `GIT binary patch`, a diff that is not UTF-8, an unreadable hunk header, a hunk before any header, a path named twice, a failed `git diff` (`test_r_every_unreadable_form_makes_the_whole_record_unreadable`) and a missing or unresolvable base or head (`test_r_a_missing_base_or_head_is_unreadable_and_never_raises`).
- G14 (C9, a removed line whose innermost test span opens on an uncited line refuses): representative the flagged test removed together with the unflagged test after it in one stretch; it groups a whole file removed with one of its four tests cited (`test_c9_a_whole_file_removal_with_one_cited_test_of_four_refuses`), an uncited opening on a range's first or last line (`test_c9_an_uncited_opening_on_a_range_boundary_refuses`), an opening a sibling that is not a worthless-test finding "cites", the file named in the detail, the tail of the test above a cited one (refusal (a)), the other lines of a test one line of which is cited (refusal (b)), a fixture line of an uncited `describe` or test class around a cited test (refusals (c1), (c2)), and an uncited `specify` beside a cited `it` read from real text (refusal (c3)). The neutralization removes the whole C9 branch, so each of these reds the same way; they were not neutralized one by one.
- G24 (the span end rule of `audits.test_spans`): representative a Python multi-line signature whose `):` sits at the opening's indent with the body after it (`[python-multi-line-signature-closer-at-the-opening-indent-and-the-body-after-it]`), with `test_c9_the_tail_of_an_uncited_python_test_read_from_real_text_refuses` as the second detector (it is the one that reds on the refusal); it groups the other cases of `test_sp_the_span_reader_reads_indentation` (the next `def` at the opening's indent, a JS `});`, an `it` inside a `describe`, end of file, a tab, a deeper closer). Refusal (a) of the order is built with hand-written spans, so it does not pass through `test_spans` and cannot detect this neutralization (see G24).
- G27 (the `_removal_files` validation of `testSpans` and `blankLines`): representative `span-openings-differ-from-openings` of `test_c2_an_absent_unreadable_or_malformed_removal_record_refuses`, the input whose acceptance gives a different refusal (C9, not C2) and so reds on the axis; it groups the other new cases of that parametrization (`spans-absent`, `blank-absent`, `span-of-length-2`, `span-start-after-opening`, `span-opening-after-end`, `span-start-zero`, `span-holds-a-bool`, `span-holds-a-float`, `spans-a-string`, `span-openings-longer-than-openings`, `spans-none-with-openings-a-list`, `spans-a-list-with-openings-none`, `blank-holds-zero`, `blank-holds-a-string`, `blank-holds-a-bool`, `blank-a-string`). The neutralization replaces the three conditions of the branch at once with the minimal defaults that keep the later code from crashing on an absent key; the cases are not neutralized one by one, and under that neutralization some of them (the length-2 span, for one) would fail by an exception and not by a wrong refusal.
- G15 (C10, `citationFresh` is exactly True): representative the string `"yes"` (`[a-string]`), the weakest input that separates "exactly True" from "truthy"; it groups `False`, an absent key, `None` and a truthy int. The neutralization is the truthiness test, so the detector reds exactly when the guard stops requiring `True`; any weaker guard (including no guard) reds the same node.
- G17 (the Python reader): representative a plain `def test_a():` line (`[def-test]`); it groups `async def test_`, `class TestX`, a tab-indented method, a spaced name, CRLF, and every non-match and over-match case of the same parametrization. The neutralization makes the pattern match nothing, the fail-open direction (a missed opening lets an unflagged test be deleted).
- G18 (the JavaScript/TypeScript reader): representative an `it(` line (`[it]`); it groups `describe`, `test`, `test.only`, `test.skip.each`, `describe.each(...)(`, a space before the parenthesis, the skipped and focused forms (`xit`, `xtest`, `xdescribe`, `fit`, `ftest`, `fdescribe`), the names added in WO-F of #2434 (`specify(`, `context(`, `suite(`, `xspecify(`, `fcontext(`, `suite.only(`, and the non-match `contextual(`; they are in this group and were not captured again, since the detector node `[it]` and the neutralization of G18 are unchanged), a tagged-template call (`test.each` then a backtick table, on one line or opening a multi-line table), and every non-match case of the same parametrization (`const t = test`, `item(`, `await it(`). The neutralization is the same match-nothing pattern.
- G19 (the unreadable base blob): representative a base file that is not UTF-8 text (read from a real git repository); it groups a base blob git cannot read at all (`test_r_a_base_blob_that_cannot_be_read_makes_the_whole_record_unreadable`), since both reach the one `base_text is None` branch.

- G20 (the sibling freshness gate): representative `citationFresh: False` on the C9 parametrization (`[false]`); it groups an absent key, the string `"yes"` and the truthy int `1` (the other three cases of that parametrization), and the C7 twin (`test_c7_a_sibling_whose_citation_is_not_exactly_fresh_ties_no_stretch`, same four cases). The neutralization deletes the whole clause, so any weaker gate reds the same node only for the inputs it lets through; the three other cases are not neutralized one by one.
- G21 (no repository or no removal head): representative a target with a resolvable repository and equal heads but no removal head (`test_f_a_finding_carried_from_an_earlier_session_has_no_removal_head_and_is_not_fresh`); it groups a missing or blank repository root (`test_f_no_repository_is_not_fresh`).
- G22 (no cited file, or a head that does not resolve): representative a target citing no file with equal heads (`test_f_equal_heads_with_no_cited_file_are_not_fresh`); it groups the unusable raised heads of `test_f_a_finding_with_no_usable_raised_head_is_not_fresh` and the unresolvable removal bases of `test_f_a_removal_base_that_does_not_resolve_is_not_fresh`, which share the one `if not files or raised is None or base is None:` branch.

G1, G2, G4, G9, G11, G12, G16, G23, G25, G26, G28 and G29 are single inputs, not grouped (G25 has two detectors, each red on its own; G26 has one).

**Listed unproven (WO-F).** None of G24-G28 is listed unproven. Two disclosures: the order's detector for G24 in its refusal form (refusal (a)) and for G25 (refusal (c1)) do not discriminate their neutralizations (hand-written spans; first refused line outside the inner span), and the detectors named in each entry are the ones that bite; the new JS names (`specify`, `context`, `suite`) are covered by G18's group without a fresh capture.

**Listed unproven (earlier legs).** None of the elements declared above is listed unproven: the three branches of `round_driver._citation_freshness` that an earlier leg listed here (no removal head or repository, no cited file or unresolved head, a changed cited file) are G21, G22 and G23 below. The grouped inputs named above run in their own test cases and were not neutralized one by one, as the grouping rule allows.

The detectors are the tests that carry a `# bite-proof:` line.

## G1. The clear arm for a test-removing `worthless-test-removed` result (`audits._AuditFold._test_removal_guard`)

- **Axis:** a clearing ruling whose `testWouldFail` answers `worthless-test-removed` stands when `test_removal_clearance` finds C1-C10 true.
- **Detector:** `test_audit_test_removal_2434.py::test_t1_a_whole_function_removal_tied_to_the_targets_line_clears`.
- **Neutralization:** `evidence, failing, detail = test_removal_clearance(f)` became `evidence, failing, detail = None, "C1", "no recorded delta"`, so the arm refuses unconditionally.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_t1_a_whole_function_removal_tied_to_the_targets_line_clears _______
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:139: in test_t1_a_whole_function_removal_tied_to_the_targets_line_clears
    assert outcome["discharged"] == ["t0"] and outcome["notDischarged"] == []
E   AssertionError: assert ([] == ['t0']
E     
E     Right contains one more item: 't0'
E     Use -v to get more diff)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_t1_a_whole_function_removal_tied_to_the_targets_line_clears
1 failed in 1.45s
exit=1
```

- **Restore:** inverse edit (the original call put back).
- **Restore receipt** (read back by the Grep tool, `evidence, failing, detail = test_removal_clearance`):

```
984:            evidence, failing, detail = test_removal_clearance(f)
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.18s
exit=0
```

## G2. C1, every file of the delta is a test path (`audits.test_removal_clearance`)

- **Axis:** a delta that names a non-test file clears nothing on the removal answer.
- **Detector:** `test_audit_test_removal_2434.py::test_c1_a_non_test_file_in_the_delta_refuses_naming_it`.
- **Neutralization:** `if other:` became `if False:`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_c1_a_non_test_file_in_the_delta_refuses_naming_it ____________
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:198: in test_c1_a_non_test_file_in_the_delta_refuses_naming_it
    reason = _refused(_fold([_removed()], _target(files=(TEST_FILE, LIB_PY), record=record)), "C1")
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:121: in _refused
    assert entry["reason"].startswith(prefix), entry["reason"]
E   AssertionError: audit check failed: testWouldFail: worthless-test-removed clears only a fix that removes test lines a worthless-test finding cites; C7: plugins/superheroes/lib/widget_2434.py lines 10-14 hold no cited line
E   assert False
E    +  where False = <built-in method startswith of str object at 0x108787230>('audit check failed: testWouldFail: worthless-test-removed clears only a fix that removes test lines a worthless-test finding cites; C1: ')
E    +    where <built-in method startswith of str object at 0x108787230> = 'audit check failed: testWouldFail: worthless-test-removed clears only a fix that removes test lines a worthless-test finding cites; C7: plugins/superheroes/lib/widget_2434.py lines 10-14 hold no cited line'.startswith
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_c1_a_non_test_file_in_the_delta_refuses_naming_it
1 failed in 1.38s
exit=1
```

- **Restore:** inverse edit (`if False:` back to `if other:`).
- **Restore receipt** (read back by the Grep tool, `    if other:`):

```
291:    if other:
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.16s
exit=0
```

## G3. C2, the removal record is readable and well formed (`audits._removal_files`)

- **Axis:** a removal record that is absent, `unreadable` or malformed clears nothing; this entry proves the malformed-range input (grouping above).
- **Detector:** `test_audit_test_removal_2434.py::test_c2_an_absent_unreadable_or_malformed_removal_record_refuses[start-after-end]`.
- **Neutralization:** `if not 1 <= pair[0] <= pair[1]:` became `if False:`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_c2_an_absent_unreadable_or_malformed_removal_record_refuses[start-after-end] _
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:253: in test_c2_an_absent_unreadable_or_malformed_removal_record_refuses
    _refused(_fold([_removed()], target), "C2")
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:121: in _refused
    assert entry["reason"].startswith(prefix), entry["reason"]
E   AssertionError: audit check failed: testWouldFail: worthless-test-removed clears only a fix that removes test lines a worthless-test finding cites; C6: no removed range holds a line the finding cites
E   assert False
E    +  where False = <built-in method startswith of str object at 0x106f22250>('audit check failed: testWouldFail: worthless-test-removed clears only a fix that removes test lines a worthless-test finding cites; C2: ')
E    +    where <built-in method startswith of str object at 0x106f22250> = 'audit check failed: testWouldFail: worthless-test-removed clears only a fix that removes test lines a worthless-test finding cites; C6: no removed range holds a line the finding cites'.startswith
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_c2_an_absent_unreadable_or_malformed_removal_record_refuses[start-after-end]
1 failed in 1.58s
exit=1
```

- **Restore:** inverse edit (`if False:` back to `if not 1 <= pair[0] <= pair[1]:`).
- **Restore receipt** (read back by the Grep tool, `if not 1 <= pair`):

```
223:            if not 1 <= pair[0] <= pair[1]:
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.17s
exit=0
```

## G4. C3, the removal record and the delta name the same files (`audits.test_removal_clearance`)

- **Axis:** a removal record whose file set differs from the delta's clears nothing.
- **Detector:** `test_audit_test_removal_2434.py::test_c3_a_removal_record_and_a_delta_that_name_different_files_refuse`.
- **Neutralization:** `if {path for path, _r, _a, _o in rows} != set(files):` became `if False:`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_c3_a_removal_record_and_a_delta_that_name_different_files_refuse _____
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:261: in test_c3_a_removal_record_and_a_delta_that_name_different_files_refuse
    _refused(_fold([_removed()], _target(record=_record(_row(OTHER_TEST_FILE)))), "C3")
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:121: in _refused
    assert entry["reason"].startswith(prefix), entry["reason"]
E   AssertionError: audit check failed: testWouldFail: worthless-test-removed clears only a fix that removes test lines a worthless-test finding cites; C6: no removed range holds a line the finding cites
E   assert False
E    +  where False = <built-in method startswith of str object at 0x106aaa170>('audit check failed: testWouldFail: worthless-test-removed clears only a fix that removes test lines a worthless-test finding cites; C3: ')
E    +    where <built-in method startswith of str object at 0x106aaa170> = 'audit check failed: testWouldFail: worthless-test-removed clears only a fix that removes test lines a worthless-test finding cites; C6: no removed range holds a line the finding cites'.startswith
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_c3_a_removal_record_and_a_delta_that_name_different_files_refuse
1 failed in 1.17s
exit=1
```

- **Restore:** inverse edit (`if False:` back to the set comparison).
- **Restore receipt** (read back by the Grep tool, `!= set\(files\)`):

```
298:    if {path for path, _r, _a, _o in rows} != set(files):
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.39s
exit=0
```

## G5. C4, the fix added nothing (`audits.test_removal_clearance`)

- **Axis:** a file whose record says `added: True` clears nothing on the removal answer; this entry proves that input (grouping above).
- **Detector:** `test_audit_test_removal_2434.py::test_c4_a_file_that_added_a_line_refuses`.
- **Neutralization:** `if added is not False:` became `if False:`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________________ test_c4_a_file_that_added_a_line_refuses ___________________
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:271: in test_c4_a_file_that_added_a_line_refuses
    reason = _refused(_fold([_removed()], _target(record=_record(_row(added=True)))), "C4")
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:116: in _refused
    assert outcome["discharged"] == [] and outcome["notDischarged"] == ["t0"]
E   AssertionError: assert (['t0'] == []
E     
E     Left contains one more item: 't0'
E     Use -v to get more diff)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_c4_a_file_that_added_a_line_refuses
1 failed in 1.36s
exit=1
```

- **Restore:** inverse edit (`if False:` back to `if added is not False:`).
- **Restore receipt** (read back by the Grep tool, `if added is not False`):

```
302:        if added is not False:
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.31s
exit=0
```

## G6. C5, the target is a worthless-test finding (`audits._worthless_test_smell`)

- **Axis:** a target that is not a Test finding with a worthless smell and a usable body clears nothing; this entry proves the wrong-dimension input (grouping above).
- **Detector:** `test_audit_test_removal_2434.py::test_c5_a_target_that_is_not_a_worthless_test_finding_refuses[wrong-dimension]`.
- **Neutralization:** `if finding.get("dimension") != "Test":` became `if False:`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_c5_a_target_that_is_not_a_worthless_test_finding_refuses[wrong-dimension] _
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:297: in test_c5_a_target_that_is_not_a_worthless_test_finding_refuses
    _refused(_fold([_removed()], _target(**change)), "C5")
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:116: in _refused
    assert outcome["discharged"] == [] and outcome["notDischarged"] == ["t0"]
E   AssertionError: assert (['t0'] == []
E     
E     Left contains one more item: 't0'
E     Use -v to get more diff)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_c5_a_target_that_is_not_a_worthless_test_finding_refuses[wrong-dimension]
1 failed in 1.22s
exit=1
```

- **Restore:** inverse edit (`if False:` back to `if finding.get("dimension") != "Test":`).
- **Restore receipt** (read back by the Grep tool, `dimension"\) != "Test"`):

```
237:    if finding.get("dimension") != "Test":
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.58s
exit=0
```

## G7. C6, one of the target's own cited lines lies in a removed range (`audits.test_removal_clearance`)

- **Axis:** a removal holding none of the target's own cited lines clears nothing; this entry proves the line-outside-every-range input (grouping above).
- **Detector:** `test_audit_test_removal_2434.py::test_c6_a_removal_holding_none_of_the_targets_lines_refuses`.
- **Neutralization:** `if not any(_inside(own, path, rng) for path, ranges, _a, _o in rows for rng in ranges):` became `if False:`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_c6_a_removal_holding_none_of_the_targets_lines_refuses __________
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:305: in test_c6_a_removal_holding_none_of_the_targets_lines_refuses
    _refused(_fold([_removed()], _target(line=30)), "C6")
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:121: in _refused
    assert entry["reason"].startswith(prefix), entry["reason"]
E   AssertionError: audit check failed: testWouldFail: worthless-test-removed clears only a fix that removes test lines a worthless-test finding cites; C7: plugins/superheroes/lib/tests/test_widget_2434.py lines 10-14 hold no cited line
E   assert False
E    +  where False = <built-in method startswith of str object at 0x1085b98a0>('audit check failed: testWouldFail: worthless-test-removed clears only a fix that removes test lines a worthless-test finding cites; C6: ')
E    +    where <built-in method startswith of str object at 0x1085b98a0> = 'audit check failed: testWouldFail: worthless-test-removed clears only a fix that removes test lines a worthless-test finding cites; C7: plugins/superheroes/lib/tests/test_widget_2434.py lines 10-14 hold no cited line'.startswith
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_c6_a_removal_holding_none_of_the_targets_lines_refuses
1 failed in 2.38s
exit=1
```

- **Restore:** inverse edit (`if False:` back to the `any(...)` test).
- **Restore receipt** (read back by the Grep tool, `if not any\(_inside\(own`):

```
322:    if not any(_inside(own, path, rng) for path, ranges, _a, _o in rows for rng in ranges):
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.19s
exit=0
```

## G8. C7, a removed line outside every test span needs a cited line in its range (`audits.test_removal_clearance`)

Re-captured in WO-F of #2434 for the per-line C7 (the first capture was of the per-range branch it replaces).

- **Axis:** a removed line that lies in no test span (`testSpans`), is neither cited nor blank (`blankLines`), and whose removed range holds no line cited by the target or a fresh worthless-smell sibling clears nothing, so the fix cannot also delete an uncited helper or fixture; this entry proves the extra-range input (grouping above).
- **Detector:** `test_audit_test_removal_2434.py::test_c7_a_removed_range_holding_no_cited_line_refuses`.
- **Neutralization:** `if not _inside(cited, path, rng) and any(` became `if False and any(` (the C7 branch never refuses).

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_c7_a_removed_range_holding_no_cited_line_refuses _____________
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:373: in test_c7_a_removed_range_holding_no_cited_line_refuses
    reason = _refused(_fold([_removed()], _target(record=_two_ranges())), "C7")
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:130: in _refused
    assert outcome["discharged"] == [] and outcome["notDischarged"] == ["t0"]
E   AssertionError: assert (['t0'] == []
E     
E     Left contains one more item: 't0'
E     Use -v to get more diff)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_c7_a_removed_range_holding_no_cited_line_refuses
1 failed in 1.46s
exit=1
```

- **Restore:** inverse edit (`if False and any(` back to `if not _inside(cited, path, rng) and any(`).
- **Restore receipt** (read back by the Grep tool, `if not _inside\(cited, path, rng\) and any\(`):

```
387:            if not _inside(cited, path, rng) and any(
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.50s
exit=0
```

## G9. The `added` detection (`round_driver._fixer_removal`)

- **Axis:** any hunk with a new-side line count above zero marks its file `added: True`.
- **Detector:** `test_audit_test_removal_2434.py::test_r_a_replacement_and_a_new_file_mark_their_files_as_added_to`.
- **Neutralization:** `if new_count > 0:` became `if False:`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_r_a_replacement_and_a_new_file_mark_their_files_as_added_to _______
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:731: in test_r_a_replacement_and_a_new_file_mark_their_files_as_added_to
    assert _files(_removal(repo, base, head)) == {TFILE: ([[2, 2]], True), "tests/test_new.py": ([], True)}
E   AssertionError: assert {'tests/test_...: ([], False)} == {'tests/test_...': ([], True)}
E     
E     Differing items:
E     {'tests/test_a.py': ([[2, 2]], False)} != {'tests/test_a.py': ([[2, 2]], True)}
E     {'tests/test_new.py': ([], False)} != {'tests/test_new.py': ([], True)}
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_r_a_replacement_and_a_new_file_mark_their_files_as_added_to
1 failed in 6.15s
exit=1
```

- **Restore:** inverse edit (`if False:` back to `if new_count > 0:`).
- **Restore receipt** (read back by the Grep tool, `if new_count > 0`):

```
7021:            if new_count > 0:
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 4.58s
exit=0
```

## G10. The unreadable detection (`round_driver._fixer_removal`)

- **Axis:** a binary file in the diff makes the whole record unreadable; this entry proves the real-binary-file input (grouping above).
- **Detector:** `test_audit_test_removal_2434.py::test_r_a_binary_file_makes_the_whole_record_unreadable`.
- **Neutralization:** `elif line.startswith("Binary files ") or line.startswith("GIT binary patch"):` became `elif False:`.

**Raw red** (exit 1; the `...` inside the assertion line is pytest's own truncation of a long repr, not an edit):

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_r_a_binary_file_makes_the_whole_record_unreadable ____________
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:742: in test_r_a_binary_file_makes_the_whole_record_unreadable
    assert "unreadable" in record and "files" not in record
E   AssertionError: assert ('unreadable' in {'base': 'a9431fbc0d5049a143d94c613d3ab804c6483e1c', 'head': '6cd153cc8eda587884619b6785851fc7f4bbf737', 'files': [{'p...ed': False, 'testOpenings': []}, {'path': 'tests/test_a.py', 'removed': [[2, 8]], 'added': False, 'testOpenings': []}]})
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_r_a_binary_file_makes_the_whole_record_unreadable
1 failed in 5.28s
exit=1
```

- **Restore:** inverse edit (`elif False:` back to the two `startswith` tests).
- **Restore receipt** (read back by the Grep tool, `elif line.startswith\("Binary files `):

```
7008:        elif line.startswith("Binary files ") or line.startswith("GIT binary patch"):
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 2.77s
exit=0
```

## G11. `--no-textconv` (`round_driver._fixer_removal`)

- **Axis:** a configured textconv never shapes the record: the diff is asked for with `--no-textconv`.
- **Detector:** `test_audit_test_removal_2434.py::test_r_a_configured_textconv_never_hides_an_added_line`.
- **Neutralization:** the `"--no-textconv", ` argument was removed from the `git diff` call.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_r_a_configured_textconv_never_hides_an_added_line ____________
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:831: in test_r_a_configured_textconv_never_hides_an_added_line
    assert _files(_removal(repo, base, head)) == {"tests/test_a.txt": ([], True)}
E   AssertionError: assert {} == {'tests/test_...': ([], True)}
E     
E     Right contains 1 more item:
E     {'tests/test_a.txt': ([], True)}
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_r_a_configured_textconv_never_hides_an_added_line
1 failed in 2.84s
exit=1
```

- **Restore:** inverse edit (the argument put back).
- **Restore receipt** (read back by the Grep tool, `"--no-ext-diff", "--no-textconv", "--no-color"`):

```
6989:    raw = _git_bytes(repo_root, "diff", "--no-ext-diff", "--no-textconv", "--no-color", "--src-prefix=a/",
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 3.11s
exit=0
```

## G12. The explicit endpoint (`round_driver._fixer_removal`)

- **Axis:** the record describes `base..head` for the explicit head commit, never the live checkout HEAD.
- **Detector:** `test_audit_test_removal_2434.py::test_r_the_record_describes_the_explicit_head_not_the_checkout`.
- **Neutralization:** `shas[0], shas[1])` at the end of the `git diff` call became `shas[0], "HEAD")`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_r_the_record_describes_the_explicit_head_not_the_checkout ________
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:845: in test_r_the_record_describes_the_explicit_head_not_the_checkout
    assert _files(record) == {TFILE: ([], True)}
E   AssertionError: assert {'tests/test_..., 1]], False)} == {'tests/test_...': ([], True)}
E     
E     Differing items:
E     {'tests/test_a.py': ([[1, 1]], False)} != {'tests/test_a.py': ([], True)}
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_r_the_record_describes_the_explicit_head_not_the_checkout
1 failed in 3.34s
exit=1
```

- **Restore:** inverse edit (`"HEAD")` back to `shas[1])`).
- **Restore receipt** (read back by the Grep tool, `"--inter-hunk-context=0", shas\[0\], shas\[1\]\)`):

```
6990:                     "--dst-prefix=b/", "--no-renames", "--unified=0", "--inter-hunk-context=0", shas[0], shas[1])
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 3.30s
exit=0
```

## G13. C8, every changed file is in a language the test-opening reader supports (`audits.test_removal_clearance`)

- **Axis:** a changed file whose language has no test-opening reader (`testOpenings` is `None`) clears nothing on the removal answer, so the fix cannot delete tests the driver cannot count.
- **Detector:** `test_audit_test_removal_2434.py::test_c8_a_changed_file_in_an_unsupported_language_refuses_naming_it`.
- **Neutralization:** `if openings is None:` (in the C8 loop) became `if False:`. With C8 gone the `.rb` file's `None` reaches the C9 loop, which raises; the red below is that crash, so the detector reds whether the weakened code crashes or clears.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_c8_a_changed_file_in_an_unsupported_language_refuses_naming_it ______
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:384: in test_c8_a_changed_file_in_an_unsupported_language_refuses_naming_it
    assert RB_TEST_FILE in _refused(_fold([_removed()], only), "C8")
                                    ^^^^^^^^^^^^^^^^^^^^^^^^^
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:106: in _fold
    return audits.apply_audit_results([target], results, collection_manifest={"t0": "codex"})
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<worktree>/plugins/superheroes/lib/audits.py:1228: in apply_audit_results
    fold.fold_target(f)
<worktree>/plugins/superheroes/lib/audits.py:735: in fold_target
    finished, removal = self._test_removal_guard(base, fid, f, r, ruling)
                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<worktree>/plugins/superheroes/lib/audits.py:984: in _test_removal_guard
    evidence, failing, detail = test_removal_clearance(f)
                                ^^^^^^^^^^^^^^^^^^^^^^^^^
<worktree>/plugins/superheroes/lib/audits.py:335: in test_removal_clearance
    within = sorted({n for n in openings if any(rng[0] <= n <= rng[1] for rng in ranges)})
                                ^^^^^^^^
E   TypeError: 'NoneType' object is not iterable
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_c8_a_changed_file_in_an_unsupported_language_refuses_naming_it
1 failed in 1.14s
exit=1
```

- **Restore:** inverse edit (`if False:` back to `if openings is None:`).
- **Restore receipt** (read back by the Grep tool, `if openings is None:`):

```
331:        if openings is None:
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 2.19s
exit=0
```

## G14. C9, a removed line whose innermost test span opens on an uncited line refuses (`audits.test_removal_clearance`)

Re-captured in WO-F of #2434 for the per-line C9 (the first capture was of the per-opening branch it replaces).

- **Axis:** a removed line that is neither cited nor blank and whose innermost test span (the containing span with the greatest start) opens on a line no finding cites clears nothing, so a stretch that takes a flagged test together with an unflagged one is refused; this entry proves the adjacent-test input (grouping above).
- **Detector:** `test_audit_test_removal_2434.py::test_c9_a_stretch_that_removes_a_cited_test_and_the_uncited_test_after_it_refuses`.
- **Neutralization:** `if inner is not None and not _tied(path, line, blank) and (path, inner[1]) not in cited_set:` became `if False:`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_c9_a_stretch_that_removes_a_cited_test_and_the_uncited_test_after_it_refuses _
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:467: in test_c9_a_stretch_that_removes_a_cited_test_and_the_uncited_test_after_it_refuses
    reason = _refused(_fold([_removed()], _target(line=10, record=record)), "C9")
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:130: in _refused
    assert outcome["discharged"] == [] and outcome["notDischarged"] == ["t0"]
E   AssertionError: assert (['t0'] == []
E     
E     Left contains one more item: 't0'
E     Use -v to get more diff)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_c9_a_stretch_that_removes_a_cited_test_and_the_uncited_test_after_it_refuses
1 failed in 2.37s
exit=1
```

- **Restore:** inverse edit (`if False:` back to `if inner is not None and not _tied(path, line, blank) and (path, inner[1]) not in cited_set:`).
- **Restore receipt** (read back by the Grep tool, `if inner is not None and not _tied`):

```
400:                if inner is not None and not _tied(path, line, blank) and (path, inner[1]) not in cited_set:
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.30s
exit=0
```

## G15. C10, `citationFresh` is exactly True (`audits.test_removal_clearance`)

- **Axis:** a target whose `citationFresh` is not exactly `True` (false, absent, a string, `None`, a truthy int) clears nothing, so a cited line that may have moved ties nothing; this entry proves the string input, the one that separates "exactly True" from "truthy" (grouping above).
- **Detector:** `test_audit_test_removal_2434.py::test_c10_a_target_whose_citation_is_not_exactly_fresh_refuses[a-string]`.
- **Neutralization:** `if target.get("citationFresh") is not True:` became `if not target.get("citationFresh"):`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_c10_a_target_whose_citation_is_not_exactly_fresh_refuses[a-string] ____
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:466: in test_c10_a_target_whose_citation_is_not_exactly_fresh_refuses
    reason = _refused(_fold([_removed()], _target(citationFresh=fresh)), "C10")
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:116: in _refused
    assert outcome["discharged"] == [] and outcome["notDischarged"] == ["t0"]
E   AssertionError: assert (['t0'] == []
E     
E     Left contains one more item: 't0'
E     Use -v to get more diff)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_c10_a_target_whose_citation_is_not_exactly_fresh_refuses[a-string]
1 failed in 1.07s
exit=1
```

- **Restore:** inverse edit (`if not target.get("citationFresh"):` back to `if target.get("citationFresh") is not True:`).
- **Restore receipt** (read back by the Grep tool, `citationFresh"\) is not True`):

```
342:    if target.get("citationFresh") is not True:
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.89s
exit=0
```

## G16. `--inter-hunk-context=0` (`round_driver._fixer_removal`)

- **Axis:** a configured `diff.interHunkContext` never merges two deleted stretches with an unchanged line between them into one range (which one cited line could then tie): the diff is asked for with `--inter-hunk-context=0`.
- **Detector:** `test_audit_test_removal_2434.py::test_r_two_deletions_with_a_kept_line_between_them_stay_two_ranges_whatever_git_is_configured_to`.
- **Neutralization:** the `"--inter-hunk-context=0", ` argument was removed from the `git diff` call.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_r_two_deletions_with_a_kept_line_between_them_stay_two_ranges_whatever_git_is_configured_to _
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:869: in test_r_two_deletions_with_a_kept_line_between_them_stay_two_ranges_whatever_git_is_configured_to
    assert _files(_removal(repo, base, head)) == {TFILE: ([[2, 2], [4, 4]], False)}
E   AssertionError: assert {'tests/test_...2, 4]], True)} == {'tests/test_..., 4]], False)}
E     
E     Differing items:
E     {'tests/test_a.py': ([[2, 4]], True)} != {'tests/test_a.py': ([[2, 2], [4, 4]], False)}
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_r_two_deletions_with_a_kept_line_between_them_stay_two_ranges_whatever_git_is_configured_to
1 failed in 2.80s
exit=1
```

- **Restore:** inverse edit (the argument put back after `"--unified=0", `).
- **Restore receipt** (read back by the Grep tool, `"--unified=0", "--inter-hunk-context=0"`):

```
6990:                     "--dst-prefix=b/", "--no-renames", "--unified=0", "--inter-hunk-context=0", shas[0], shas[1])
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 3.00s
exit=0
```

## G17. The Python test-opening reader (`audits.PYTHON_TEST_OPENING`, read by `audits.test_openings`)

- **Axis:** a `.py` file's test openings are the lines that start a `def test...`, `async def test...` or `class Test...`; a reader that finds none lets a flagged test be deleted together with unflagged ones unseen.
- **Detector:** `test_audit_test_removal_2434.py::test_o_the_python_reader_reads_def_test_and_class_test_lines[def-test]`.
- **Neutralization:** `PYTHON_TEST_OPENING = re.compile(r"^\s*(async\s+)?def\s+test\w*\s*\(|^\s*class\s+Test\w*\b")` became `PYTHON_TEST_OPENING = re.compile(r"(?!)")`, a pattern that matches nothing.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_o_the_python_reader_reads_def_test_and_class_test_lines[def-test] ____
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:498: in test_o_the_python_reader_reads_def_test_and_class_test_lines
    assert audits.test_openings("tests/test_a.py", text) == expected
E   assert [] == [1]
E     
E     Right contains one more item: 1
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_o_the_python_reader_reads_def_test_and_class_test_lines[def-test]
1 failed in 1.43s
exit=1
```

- **Restore:** inverse edit (the original pattern put back).
- **Restore receipt** (read back by the Grep tool, `^PYTHON_TEST_OPENING`):

```
171:PYTHON_TEST_OPENING = re.compile(r"^\s*(async\s+)?def\s+test\w*\s*\(|^\s*class\s+Test\w*\b")
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.99s
exit=0
```

## G18. The JavaScript/TypeScript test-opening reader (`audits.JS_TEST_OPENING`, read by `audits.test_openings`)

- **Axis:** a `.js`, `.jsx`, `.mjs`, `.cjs`, `.ts`, `.tsx`, `.mts` or `.cts` file's test openings are the lines that start an `it(`, `test(` or `describe(` call (with any `.modifier`); a reader that finds none lets a flagged test be deleted together with unflagged ones unseen.
- **Detector:** `test_audit_test_removal_2434.py::test_o_the_js_reader_reads_it_test_and_describe_calls[it]`.
- **Neutralization:** `JS_TEST_OPENING = re.compile(r"^\s*(it|test|describe)(\.\w+)*\s*\(")` became `JS_TEST_OPENING = re.compile(r"(?!)")`, a pattern that matches nothing.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_o_the_js_reader_reads_it_test_and_describe_calls[it] ___________
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:517: in test_o_the_js_reader_reads_it_test_and_describe_calls
    assert audits.test_openings("tests/a.test.js", text) == expected
E   assert [] == [1]
E     
E     Right contains one more item: 1
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_o_the_js_reader_reads_it_test_and_describe_calls[it]
1 failed in 0.96s
exit=1
```

- **Restore:** inverse edit (the original pattern put back).
- **Restore receipt** (read back by the Grep tool, `^JS_TEST_OPENING`):

```
172:JS_TEST_OPENING = re.compile(r"^\s*(it|test|describe)(\.\w+)*\s*\(")
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.09s
exit=0
```

## G19. The unreadable base blob (`round_driver._fixer_removal`)

- **Axis:** a base file with a removed range that cannot be read, or is not UTF-8 text, makes the whole record unreadable, so its test openings are never guessed; this entry proves the not-UTF-8 input (grouping above).
- **Detector:** `test_audit_test_removal_2434.py::test_r_a_base_blob_that_is_not_utf8_makes_the_whole_record_unreadable`.
- **Neutralization:** `if base_text is None:` became `if False:`. With the branch gone the unreadable text reaches `audits.test_openings`, which raises; the red below is that crash, so the detector reds whether the weakened code crashes or records a guess.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_r_a_base_blob_that_is_not_utf8_makes_the_whole_record_unreadable _____
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:898: in test_r_a_base_blob_that_is_not_utf8_makes_the_whole_record_unreadable
    record = _removal(repo, base, head)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:707: in _removal
    return RD._fixer_removal({"repoRoot": str(repo)}, base, head)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<worktree>/plugins/superheroes/lib/round_driver.py:7035: in _fixer_removal
    entry["testOpenings"] = audits.test_openings(entry["path"], base_text)
                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<worktree>/plugins/superheroes/lib/audits.py:188: in test_openings
    return [number for number, line in enumerate(text.split("\n"), 1) if pattern.match(line)]
                                                 ^^^^^^^^^^
E   AttributeError: 'NoneType' object has no attribute 'split'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_r_a_base_blob_that_is_not_utf8_makes_the_whole_record_unreadable
1 failed in 2.22s
exit=1
```

- **Restore:** inverse edit (`if False:` back to `if base_text is None:`).
- **Restore receipt** (read back by the Grep tool, `if base_text is None:`):

```
7033:        if base_text is None:
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.95s
exit=0
```

## G20. The sibling freshness gate (`audits.test_removal_clearance`, the sibling loop)

- **Axis:** a batch sibling lends its cited lines to C7 and C9 only when it passes C5 AND its driver-built `citationFresh` is exactly `True`; a stale, absent, string or int `citationFresh` lends nothing, so a line that may have moved ties no removed stretch and opens no test. This entry proves the `False` input (grouping above).
- **Detector:** `test_audit_test_removal_2434.py::test_c9_a_sibling_whose_citation_is_not_exactly_fresh_cites_no_opening[false]`.
- **Neutralization:** `if _worthless_test_smell(sibling)[0] is not None and sibling.get("citationFresh") is True:` became `if _worthless_test_smell(sibling)[0] is not None:` (the clause `and sibling.get("citationFresh") is True` deleted).

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_c9_a_sibling_whose_citation_is_not_exactly_fresh_cites_no_opening[false] _
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:475: in test_c9_a_sibling_whose_citation_is_not_exactly_fresh_cites_no_opening
    assert "line 15 " in _refused(_fold([_removed()], target), "C9")
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:118: in _refused
    assert outcome["discharged"] == [] and outcome["notDischarged"] == ["t0"]
E   AssertionError: assert (['t0'] == []
E     
E     Left contains one more item: 't0'
E     Use -v to get more diff)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_c9_a_sibling_whose_citation_is_not_exactly_fresh_cites_no_opening[false]
1 failed in 0.91s
exit=1
```

- **Restore:** inverse edit (`and sibling.get("citationFresh") is True` put back).
- **Restore receipt** (read back by the Grep tool, `sibling.get\("citationFresh"\) is True`):

```
316:        if _worthless_test_smell(sibling)[0] is not None and sibling.get("citationFresh") is True:
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.05s
exit=0
```

## G21. `_citation_freshness`, no repository or no removal head (`round_driver._citation_freshness`)

- **Axis:** a target with no repository root or no removal head (a finding carried over from an earlier session) is never fresh, even when the raised head and the removal base are equal and resolve.
- **Detector:** `test_audit_test_removal_2434.py::test_f_a_finding_carried_from_an_earlier_session_has_no_removal_head_and_is_not_fresh`.
- **Neutralization:** `if not (_nonempty_str(repo_root) and _nonempty_str(removal_head)):` became `if False:`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_f_a_finding_carried_from_an_earlier_session_has_no_removal_head_and_is_not_fresh _
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:1217: in test_f_a_finding_carried_from_an_earlier_session_has_no_removal_head_and_is_not_fresh
    assert row["citationFresh"] is False and "unreadable" in row["fixerRemoval"]
E   assert (True is False)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_f_a_finding_carried_from_an_earlier_session_has_no_removal_head_and_is_not_fresh
1 failed in 2.24s
exit=1
```

- **Restore:** inverse edit (`if False:` back to the `_nonempty_str` test).
- **Restore receipt** (read back by the Grep tool, `if not \(_nonempty_str\(repo_root\)`; the other three lines are other functions' guards):

```
6978:    if not (_nonempty_str(repo_root) and _nonempty_str(base) and _nonempty_str(head)):
8967:    if not (_nonempty_str(repo_root) and _nonempty_str(base) and _nonempty_str(head) and _nonempty_str(path)
9079:    if not (_nonempty_str(repo_root) and _nonempty_str(commit)) or commit.startswith("-"):
9118:    if not (_nonempty_str(repo_root) and _nonempty_str(removal_head)):
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.81s
exit=0
```

## G22. `_citation_freshness`, no cited file or a head that does not resolve (`round_driver._citation_freshness`)

- **Axis:** a target that cites no file, or whose raised head or removal base does not resolve to a commit, is never fresh, even when the heads are equal; this entry proves the no-cited-file input (grouping above).
- **Detector:** `test_audit_test_removal_2434.py::test_f_equal_heads_with_no_cited_file_are_not_fresh`.
- **Neutralization:** `if not files or raised is None or base is None:` became `if False:`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_f_equal_heads_with_no_cited_file_are_not_fresh ______________
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:1167: in test_f_equal_heads_with_no_cited_file_are_not_fresh
    assert row["citationFresh"] is False
E   assert True is False
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_f_equal_heads_with_no_cited_file_are_not_fresh
1 failed in 2.38s
exit=1
```

- **Restore:** inverse edit (`if False:` back to `if not files or raised is None or base is None:`).
- **Restore receipt** (read back by the Grep tool, `if not files or raised is None or base is None:`):

```
9124:    if not files or raised is None or base is None:
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 2.34s
exit=0
```

## G23. `_citation_freshness`, a cited file that changed (`round_driver._citation_freshness`)

- **Axis:** a cited file that differs between the head the finding was raised on and the removal base makes the citation stale (the `git diff --quiet` answer decides), so a cited line that may have moved is not trusted.
- **Detector:** `test_audit_test_removal_2434.py::test_f_a_cited_file_changed_between_the_raised_head_and_the_base_is_stale`.
- **Neutralization:** `return unchanged is not None, check` became `return True, check`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_f_a_cited_file_changed_between_the_raised_head_and_the_base_is_stale ___
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:1127: in test_f_a_cited_file_changed_between_the_raised_head_and_the_base_is_stale
    assert row["citationFresh"] is False
E   assert True is False
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_f_a_cited_file_changed_between_the_raised_head_and_the_base_is_stale
1 failed in 3.05s
exit=1
```

- **Restore:** inverse edit (`return True, check` back to `return unchanged is not None, check`).
- **Restore receipt** (read back by the Grep tool, `return unchanged is not None, check`):

```
9130:    return unchanged is not None, check
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 2.81s
exit=0
```

## G24. The span end rule (`audits.test_spans`)

- **Axis:** a test's span runs over every following line indented deeper than its opening, blank lines skipped, and over a closer (`}`, `)`, `]`) at the opening's own indent, then stops at the next line at that indent; a reader whose span stops at the opening leaves the tail of an uncited test outside every span, where C7's rule (not C9's) judges it.
- **Detectors:** `test_audit_test_removal_2434.py::test_sp_the_span_reader_reads_indentation[python-multi-line-signature-closer-at-the-opening-indent-and-the-body-after-it]` (the reader) and `test_audit_test_removal_2434.py::test_c9_the_tail_of_an_uncited_python_test_read_from_real_text_refuses` (the refusal, through the reader on real text). Refusal (a) of the order, `test_c9_a_stretch_that_takes_the_tail_of_the_uncited_test_above_a_cited_one_refuses`, is built with hand-written spans, never passes through `test_spans`, and so cannot go red on this neutralization; it is the G14 detector for the tail input, not G24's.
- **Neutralization:** `if _indent(line) > indent or (_indent(line) == indent and line.lstrip()[0] in "})]"):` became `if False:`, so every span ends at its opening (`end = opening`).

**Raw red, reader** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_sp_the_span_reader_reads_indentation[python-multi-line-signature-closer-at-the-opening-indent-and-the-body-after-it] _
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:785: in test_sp_the_span_reader_reads_indentation
    assert spans == expected
E   assert [[1, 1, 1]] == [[1, 1, 5]]
E     
E     At index 0 diff: [1, 1, 1] != [1, 1, 5]
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_sp_the_span_reader_reads_indentation[python-multi-line-signature-closer-at-the-opening-indent-and-the-body-after-it]
1 failed in 1.51s
exit=1
```

(The node sat at line 785 when this red ran; two precondition assertions above it were removed afterwards, see below, so it now sits two lines higher.)

**Raw red, real-text refusal** (exit 1). The first red of this node failed on a precondition (`assert audits.test_spans(...) == [[1, 1, 3], [5, 5, 6]]`, which the reader node already pins); that assertion was removed from the detector and the red re-run, so the red below is on the C9 refusal, and the detector was unedited between this red and the green:

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_c9_the_tail_of_an_uncited_python_test_read_from_real_text_refuses ____
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:577: in test_c9_the_tail_of_an_uncited_python_test_read_from_real_text_refuses
    _detail(_refused(_fold([_removed()], _target(line=5, record=record)), "C9"), 3, 1)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:130: in _refused
    assert outcome["discharged"] == [] and outcome["notDischarged"] == ["t0"]
E   AssertionError: assert (['t0'] == []
E     
E     Left contains one more item: 't0'
E     Use -v to get more diff)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_c9_the_tail_of_an_uncited_python_test_read_from_real_text_refuses
1 failed in 1.39s
exit=1
```

- **Restore:** inverse edit (`if False:` back to the original condition).
- **Restore receipt** (read back by the Grep tool, `line.lstrip\(\)\[0\] in`):

```
219:            if _indent(line) > indent or (_indent(line) == indent and line.lstrip()[0] in "})]"):
```

**Raw green, reader** (exit 0):

```
.                                                                        [100%]
1 passed in 1.39s
exit=0
```

**Raw green, real-text refusal** (exit 0):

```
.                                                                        [100%]
1 passed in 1.41s
exit=0
```

## G25. The innermost-span choice in C9 (`audits.test_removal_clearance`)

- **Axis:** of the spans that contain a removed line, the one with the greatest start (the innermost) decides whether the line is tied; a choice of the smallest start (the outermost) refuses a cited inner test deleted from inside an uncited `describe` and clears an uncited inner test inside a cited `describe`.
- **Detectors:** `test_audit_test_removal_2434.py::test_c9_an_inner_uncited_test_inside_a_cited_describe_refuses_its_lines` and `test_audit_test_removal_2434.py::test_c9_a_cited_inner_it_deleted_from_inside_an_uncited_describe_clears` (each red on its own).
- **Disclosure, order detector that does not bite:** the order named refusal (c1), `test_c9_a_fixture_line_of_an_uncited_describe_around_a_cited_inner_it_refuses`, as G25's detector. Its first refused line (line 2) lies in the describe's span only, so the innermost and the outermost choice agree on it; it stayed green under this neutralization (the third capture below). It is not a G25 detector and carries no G25 axis line; the two tests above are.
- **Neutralization:** `inner = max((s for s in spans if s[0] <= line <= s[2]), key=lambda s: s[0], default=None)` became the same with `min(` for `max(` (the containing span with the smallest start).

**Raw red, uncited inner test inside a cited describe** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_c9_an_inner_uncited_test_inside_a_cited_describe_refuses_its_lines ____
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:607: in test_c9_an_inner_uncited_test_inside_a_cited_describe_refuses_its_lines
    _detail(_refused(_fold([_removed()], _target(line=1, record=record)), "C9"), 4, 4)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:130: in _refused
    assert outcome["discharged"] == [] and outcome["notDischarged"] == ["t0"]
E   AssertionError: assert (['t0'] == []
E     
E     Left contains one more item: 't0'
E     Use -v to get more diff)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_c9_an_inner_uncited_test_inside_a_cited_describe_refuses_its_lines
1 failed in 1.51s
exit=1
```

**Raw red, cited inner it inside an uncited describe** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_c9_a_cited_inner_it_deleted_from_inside_an_uncited_describe_clears ____
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:639: in test_c9_a_cited_inner_it_deleted_from_inside_an_uncited_describe_clears
    assert outcome["testRemovalCleared"] == ["t0"]
E   AssertionError: assert [] == ['t0']
E     
E     Right contains one more item: 't0'
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_c9_a_cited_inner_it_deleted_from_inside_an_uncited_describe_clears
1 failed in 1.46s
exit=1
```

**Order detector (c1) under the same neutralization** (exit 0, green: it does not discriminate):

```
.                                                                        [100%]
1 passed in 1.35s
exit=0
```

- **Restore:** inverse edit (`min(` back to `max(`).
- **Restore receipt** (read back by the Grep tool, `inner = (max|min)\(`):

```
398:                inner = max((s for s in spans if s[0] <= line <= s[2]), key=lambda s: s[0], default=None)
```

**Raw green, uncited inner test inside a cited describe** (exit 0):

```
.                                                                        [100%]
1 passed in 1.41s
exit=0
```

**Raw green, cited inner it inside an uncited describe** (exit 0):

```
.                                                                        [100%]
1 passed in 1.42s
exit=0
```

## G26. The decorator start rule (`audits.test_spans`)

- **Axis:** a run of `@` lines at the opening's indent directly above a test belongs to that test's span (its start is the topmost of them), so a decorated cited method deleted from inside an uncited test class is tied through its own span; a start at the opening leaves the decorator line in the class's span only, where C9 refuses it.
- **Detector:** `test_audit_test_removal_2434.py::test_c9_a_decorated_cited_method_deleted_from_inside_an_uncited_test_class_clears` (the order's nested brief-check case). The first red of this node failed on a precondition (`assert audits.test_spans(...) == [[1, 1, 7], [2, 2, 3], [5, 6, 7]]`, pinned by the reader node `[decorator-run-above-a-python-test-starts-at-the-first]`); that assertion was removed and the red re-run, so the red below is on the clearance, and the detector was unedited between this red and the green.
- **Neutralization:** `while start > 1 and lines[start - 2].lstrip().startswith("@") and _indent(lines[start - 2]) == indent:` became `while False and start > 1 and ...` (start = opening).

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_c9_a_decorated_cited_method_deleted_from_inside_an_uncited_test_class_clears _
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:649: in test_c9_a_decorated_cited_method_deleted_from_inside_an_uncited_test_class_clears
    assert outcome["testRemovalCleared"] == ["t0"]
E   AssertionError: assert [] == ['t0']
E     
E     Right contains one more item: 't0'
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_c9_a_decorated_cited_method_deleted_from_inside_an_uncited_test_class_clears
1 failed in 1.86s
exit=1
```

- **Restore:** inverse edit (`while False and start > 1` back to `while start > 1`).
- **Restore receipt** (read back by the Grep tool, `while (False and )?start > 1`):

```
223:        while start > 1 and lines[start - 2].lstrip().startswith("@") and _indent(lines[start - 2]) == indent:
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.97s
exit=0
```

## G27. The `_removal_files` validation of `testSpans` and `blankLines` (`audits._removal_files`)

- **Axis:** a row whose `testSpans` or `blankLines` is absent or malformed, or whose spans do not match its `testOpenings`, makes the record unreadable (C2), so a fix is never judged on spans the driver did not build.
- **Detector:** `test_audit_test_removal_2434.py::test_c2_an_absent_unreadable_or_malformed_removal_record_refuses[span-openings-differ-from-openings]`, the representative (see the grouping above): with the validation gone this input reaches C9 and not C2.
- **Neutralization:** the three `if ...: return None` conditions of the new branch (absent keys or a None/list mismatch; a malformed or mismatched span list; a malformed `blankLines`) were replaced together by `spans = None if spans is _ABSENT else spans` and `blank = [] if blank is _ABSENT else blank`, which accept any value that is present.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_c2_an_absent_unreadable_or_malformed_removal_record_refuses[span-openings-differ-from-openings] _
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:284: in test_c2_an_absent_unreadable_or_malformed_removal_record_refuses
    _refused(_fold([_removed()], target), "C2")
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:135: in _refused
    assert entry["reason"].startswith(prefix), entry["reason"]
E   AssertionError: audit check failed: testWouldFail: worthless-test-removed clears only a fix that removes test lines a worthless-test finding cites; C9: plugins/superheroes/lib/tests/test_widget_2434.py line 10 is in the test that opens at line 11, which no finding cites
E   assert False
E    +  where False = <built-in method startswith of str object at 0x7f900e020d40>('audit check failed: testWouldFail: worthless-test-removed clears only a fix that removes test lines a worthless-test finding cites; C2: ')
E    +    where <built-in method startswith of str object at 0x7f900e020d40> = 'audit check failed: testWouldFail: worthless-test-removed clears only a fix that removes test lines a worthless-test ...plugins/superheroes/lib/tests/test_widget_2434.py line 10 is in the test that opens at line 11, which no finding cites'.startswith
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_c2_an_absent_unreadable_or_malformed_removal_record_refuses[span-openings-differ-from-openings]
1 failed in 1.49s
exit=1
```

- **Restore:** inverse edit (the two default lines back to the three original conditions).
- **Restore receipt** (read back by the Read tool, lines 259-268 of `audits.py`):

```
        spans, blank = entry.get("testSpans", _ABSENT), entry.get("blankLines", _ABSENT)
        # axis: a row whose `testSpans` or `blankLines` is absent or malformed, or whose spans do not match its `testOpenings`, makes the record unreadable — see bite-proof record audit_test_removal_2434
        if spans is _ABSENT or blank is _ABSENT or (spans is None) != (openings is None):
            return None
        if spans is not None and not (isinstance(spans, list) and all(
                isinstance(s, list) and len(s) == 3 and all(_plain_int(n) for n in s) and 1 <= s[0] <= s[1] <= s[2]
                for s in spans) and [s[1] for s in spans] == openings):
            return None
        if not (isinstance(blank, list) and all(_plain_int(n) and n >= 1 for n in blank)):
            return None
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.25s
exit=0
```

## G28. `_fixer_removal` records `testSpans` and `blankLines` (`round_driver._fixer_removal`)

- **Axis:** for a file with a removed range, `testSpans` is `audits.test_spans` of the base blob and `blankLines` the sorted base-blob lines inside the removed ranges that are blank (also for a language with no reader); a file with no removed range carries `[]` for both. The data is read from a real `git diff`, so the fold never judges a line on spans or blanks the driver did not read.
- **Detector:** `test_audit_test_removal_2434.py::test_r_the_spans_and_blank_lines_come_from_the_base_blob_of_each_file_with_a_removed_range` (a Python base file with two tests and one blank line inside the removed range, a Ruby file with a blank removed line, and an added-only file).
- **Neutralization:** `entry["blankLines"] = sorted({n for lo, hi in entry["removed"] for n in range(lo, min(hi, len(lines)) + 1) if lines[n - 1].strip() == ""})` became `entry["blankLines"] = []`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_r_the_spans_and_blank_lines_come_from_the_base_blob_of_each_file_with_a_removed_range _
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:1177: in test_r_the_spans_and_blank_lines_come_from_the_base_blob_of_each_file_with_a_removed_range
    assert rows[TFILE] == {"path": TFILE, "removed": [[2, 5]], "added": False, "testOpenings": [2, 6],
E   AssertionError: assert {'path': 'tes...: [2, 6], ...} == {'path': 'tes...: [2, 6], ...}
E     
E     Omitting 5 identical items, use -vv to show
E     Differing items:
E     {'blankLines': []} != {'blankLines': [4]}
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_r_the_spans_and_blank_lines_come_from_the_base_blob_of_each_file_with_a_removed_range
1 failed in 1.39s
exit=1
```

- **Restore:** inverse edit (`entry["blankLines"] = []` back to the `sorted({...})` expression).
- **Restore receipt** (read back by the Grep tool, `blankLines`, right after the restore; a docstring rewrap that followed moved these two lines down by one):

```
7068:        entry["blankLines"] = sorted({n for lo, hi in entry["removed"] for n in range(lo, min(hi, len(lines)) + 1)
7069-                                      if lines[n - 1].strip() == ""})
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.38s
exit=0
```

## G29. The JavaScript reader's modifier match (`audits.JS_TEST_OPENING`, the `(\.\w+)*` group)

Added in WO-H of #2434 (after vet 889). The path prefix of the build worktree in the traceback is written `<worktree>`; nothing else was redacted.

- **Axis:** a JS/TS line that is a member call on one of the six opening names (`context.save(() => {`, `suite.add(`, `test.foo(`) is read as a test opening, so a finding that cites it ties every line indented under it (`test_spans`); with the modifier match gone the same cited look-alike is not an opening, the lines under it fall into the uncited `it` around it, and the removal refuses (C9). TRANSITION.md ("Supported languages") and the `audits.test_openings` docstring state this behaviour; the detector ties the text to the code.
- **Detector:** `test_audit_test_removal_2434.py::test_c9_a_cited_member_call_on_an_opening_name_is_a_span_opening_and_ties_the_lines_under_it` (the file `it('saves', ...)` with `context.save(() => {` on line 3, cited, `[[3, 6]]` removed, built from `audits.test_openings` and `audits.test_spans` through `_read_row`; expected: it clears). Its pair `test_c9_the_same_deletion_with_a_name_that_is_not_an_opening_refuses` (`helper.save`, refuses C9 at line 4, opening 1) passes with and without the neutralization and is not a detector of this element.
- **Neutralization:** `(\.\w+)*` became `()` in `JS_TEST_OPENING` (no modifiers read; `it.only(` and `test.each(` would stop matching too).
- **Disclosure:** the detector first carried two precondition asserts (`test_openings == [1, 3]`, `test_spans == [[1, 1, 7], [3, 3, 6]]`); under the neutralization the first red landed on `assert [1] == [1, 3]` and not on the clearance. Both asserts were removed from the node and the red re-run, so the red below is on the clearance itself. The detector is unedited between the red and the green below.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_c9_a_cited_member_call_on_an_opening_name_is_a_span_opening_and_ties_the_lines_under_it _
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:615: in test_c9_a_cited_member_call_on_an_opening_name_is_a_span_opening_and_ties_the_lines_under_it
    assert outcome["testRemovalCleared"] == ["t0"]
E   AssertionError: assert [] == ['t0']
E     
E     Right contains one more item: 't0'
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_c9_a_cited_member_call_on_an_opening_name_is_a_span_opening_and_ties_the_lines_under_it
1 failed in 1.43s
exit=1
```

- **Restore:** inverse edit (`()` back to `(\.\w+)*`).
- **Restore receipt** (read back by the Grep tool, `^JS_TEST_OPENING`):

```
175:JS_TEST_OPENING = re.compile(r"^\s*(x|f)?(it|test|describe|specify|context|suite)(\.\w+)*\s*[(`]")
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.62s
exit=0
```
