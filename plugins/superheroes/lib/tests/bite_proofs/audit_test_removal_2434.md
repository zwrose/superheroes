# Bite-proof record — a fix that only removes worthless test lines clears its audit on a `worthless-test-removed` answer (#2434)

Detector file: `plugins/superheroes/lib/tests/test_audit_test_removal_2434.py`, unedited between each red and its green. Every entry is a targeted, reversible Edit-tool edit to one production file (`plugins/superheroes/lib/audits.py` for G1-G8, `plugins/superheroes/lib/round_driver.py` for G9-G12), restored by the inverse edit (no `git checkout`, `restore`, `reset` or `stash`). Runs: `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest '<exact node id>' -q -n 0 --tb=short`, one test node each, output captured whole, followed by the `exit=` line the command printed. Each `old_string` occurred exactly once (the Edit tool refuses a non-unique match). No secrets, tokens, private URLs or PII appear in any capture. One redaction: the absolute path of the build worktree, which prefixes the file paths in the tracebacks, is written `<worktree>`; nothing else was redacted.

The twelve guarded elements are the ones the order declared: G1 the clear arm, G2-G8 the refusals C1-C7, G9 the `added` detection, G10 the unreadable detection, G11 `--no-textconv`, G12 the explicit endpoint. The new answer on `right` or `brokeNothing` (a shape fault) and on a `not-discharged` ruling (no clearing, no listing) are plain tests, not guarded elements.

**Grouping** (the grouping rule of `rubric/bite-proof.md`: a class is a distinct failure mode, named by its representative, and every grouped input keeps its own test case). Each condition element proves one representative input; the inputs it groups run in the same test function or parametrization and are not neutralized one by one:

- G3 (C2, the removal record is readable and well formed): representative a range with `start > end` (`[start-after-end]`); it groups an absent record, `None`, an `unreadable` record, an empty or non-list `files`, a range with start `0`, a bool, a string or a float, a range of the wrong length or not a list, a blank or non-string path, an `added` that is not a bool, a row that is not a dict, and a path named twice.
- G5 (C4, the fix added nothing): representative `added: True`; it groups a file with no removed range (`test_c4_a_file_with_no_removed_range_refuses`).
- G6 (C5, the target is a worthless-test finding): representative a wrong dimension (`[wrong-dimension]`); it groups no or differently cased dimension, an unknown or near-miss taxonomy, a `None` or non-string taxonomy, and a blank, missing or non-string body.
- G7 (C6, one of the target's own cited lines lies in a removed range): representative a `line` outside every removed range; it groups a `line` that is `None`, a bool, a string or a float (`test_c6_a_line_that_is_not_a_plain_integer_cites_nothing`) and a sibling's line that does not supply the target's own tie (`test_c6_a_siblings_line_does_not_tie_a_removal_the_target_does_not_cite`). With C6 neutralized the first case falls through to C7 and still reds the detector, as the capture shows; the sibling case is the one whose result C6 alone decides.
- G8 (C7, every removed range holds a cited line): representative an extra range tied to nothing; it groups a sibling that fails C5 (`test_c7_a_sibling_that_is_not_a_worthless_test_finding_ties_nothing`, five cases) and a sibling that is not a dict.
- G10 (the unreadable forms of `_fixer_removal`): representative a real binary file; it groups a two-path header, a git-quoted header, a `Binary files` line, a `GIT binary patch`, a diff that is not UTF-8, an unreadable hunk header, a hunk before any header, a path named twice, a failed `git diff` (`test_r_every_unreadable_form_makes_the_whole_record_unreadable`) and a missing or unresolvable base or head (`test_r_a_missing_base_or_head_is_unreadable_and_never_raises`).

G1, G2, G4, G9, G11 and G12 are single inputs, not grouped.

The detectors are the tests that carry a `# bite-proof:` line.

## G1. The clear arm for a test-removing `worthless-test-removed` result (`audits._AuditFold._test_removal_guard`)

- **Axis:** a clearing ruling whose `testWouldFail` answers `worthless-test-removed` stands when `test_removal_clearance` finds C1-C7 true.
- **Detector:** `test_audit_test_removal_2434.py::test_t1_a_whole_function_removal_tied_to_the_targets_line_clears`.
- **Neutralization:** `evidence, failing, detail = test_removal_clearance(f)` became `evidence, failing, detail = None, "C1", "no recorded delta"`, so the arm refuses unconditionally.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_t1_a_whole_function_removal_tied_to_the_targets_line_clears _______
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:122: in test_t1_a_whole_function_removal_tied_to_the_targets_line_clears
    assert outcome["discharged"] == ["t0"] and outcome["notDischarged"] == []
E   AssertionError: assert ([] == ['t0']
E     
E     Right contains one more item: 't0'
E     Use -v to get more diff)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_t1_a_whole_function_removal_tied_to_the_targets_line_clears
1 failed in 0.57s
exit=1
```

- **Restore:** inverse edit (the original call put back).
- **Restore receipt** (read back by the Grep tool, `evidence, failing, detail = `):

```
926:            evidence, failing, detail = test_removal_clearance(f)
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.70s
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
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:180: in test_c1_a_non_test_file_in_the_delta_refuses_naming_it
    reason = _refused(_fold([_removed()], _target(files=(TEST_FILE, LIB_PY), record=record)), "C1")
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:104: in _refused
    assert entry["reason"].startswith(prefix), entry["reason"]
E   AssertionError: audit check failed: testWouldFail: worthless-test-removed clears only a fix that removes test lines a worthless-test finding cites; C7: plugins/superheroes/lib/widget_2434.py lines 10-14 hold no cited line
E   assert False
E    +  where False = <built-in method startswith of str object at 0x1088bd330>('audit check failed: testWouldFail: worthless-test-removed clears only a fix that removes test lines a worthless-test finding cites; C1: ')
E    +    where <built-in method startswith of str object at 0x1088bd330> = 'audit check failed: testWouldFail: worthless-test-removed clears only a fix that removes test lines a worthless-test finding cites; C7: plugins/superheroes/lib/widget_2434.py lines 10-14 hold no cited line'.startswith
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_c1_a_non_test_file_in_the_delta_refuses_naming_it
1 failed in 0.59s
exit=1
```

- **Restore:** inverse edit (`if False:` back to `if other:`).
- **Restore receipt** (read back by the Grep tool, `    if other:`):

```
249:    if other:
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.52s
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
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:225: in test_c2_an_absent_unreadable_or_malformed_removal_record_refuses
    _refused(_fold([_removed()], target), "C2")
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:104: in _refused
    assert entry["reason"].startswith(prefix), entry["reason"]
E   AssertionError: audit check failed: testWouldFail: worthless-test-removed clears only a fix that removes test lines a worthless-test finding cites; C6: no removed range holds a line the finding cites
E   assert False
E    +  where False = <built-in method startswith of str object at 0x10a0e8650>('audit check failed: testWouldFail: worthless-test-removed clears only a fix that removes test lines a worthless-test finding cites; C2: ')
E    +    where <built-in method startswith of str object at 0x10a0e8650> = 'audit check failed: testWouldFail: worthless-test-removed clears only a fix that removes test lines a worthless-test finding cites; C6: no removed range holds a line the finding cites'.startswith
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_c2_an_absent_unreadable_or_malformed_removal_record_refuses[start-after-end]
1 failed in 0.53s
exit=1
```

- **Restore:** inverse edit (`if False:` back to `if not 1 <= pair[0] <= pair[1]:`).
- **Restore receipt** (read back by the Grep tool, `if not 1 <= pair`):

```
188:            if not 1 <= pair[0] <= pair[1]:
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.53s
exit=0
```

## G4. C3, the removal record and the delta name the same files (`audits.test_removal_clearance`)

- **Axis:** a removal record whose file set differs from the delta's clears nothing.
- **Detector:** `test_audit_test_removal_2434.py::test_c3_a_removal_record_and_a_delta_that_name_different_files_refuse`.
- **Neutralization:** `if {path for path, _r, _a in rows} != set(files):` became `if False:`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_c3_a_removal_record_and_a_delta_that_name_different_files_refuse _____
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:233: in test_c3_a_removal_record_and_a_delta_that_name_different_files_refuse
    _refused(_fold([_removed()], _target(record=_record(_row(OTHER_TEST_FILE)))), "C3")
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:104: in _refused
    assert entry["reason"].startswith(prefix), entry["reason"]
E   AssertionError: audit check failed: testWouldFail: worthless-test-removed clears only a fix that removes test lines a worthless-test finding cites; C6: no removed range holds a line the finding cites
E   assert False
E    +  where False = <built-in method startswith of str object at 0x104df1b50>('audit check failed: testWouldFail: worthless-test-removed clears only a fix that removes test lines a worthless-test finding cites; C3: ')
E    +    where <built-in method startswith of str object at 0x104df1b50> = 'audit check failed: testWouldFail: worthless-test-removed clears only a fix that removes test lines a worthless-test finding cites; C6: no removed range holds a line the finding cites'.startswith
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_c3_a_removal_record_and_a_delta_that_name_different_files_refuse
1 failed in 0.54s
exit=1
```

- **Restore:** inverse edit (`if False:` back to the set comparison).
- **Restore receipt** (read back by the Grep tool, `!= set\(files\)`):

```
256:    if {path for path, _r, _a in rows} != set(files):
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.52s
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
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:243: in test_c4_a_file_that_added_a_line_refuses
    reason = _refused(_fold([_removed()], _target(record=_record(_row(added=True)))), "C4")
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:99: in _refused
    assert outcome["discharged"] == [] and outcome["notDischarged"] == ["t0"]
E   AssertionError: assert (['t0'] == []
E     
E     Left contains one more item: 't0'
E     Use -v to get more diff)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_c4_a_file_that_added_a_line_refuses
1 failed in 0.55s
exit=1
```

- **Restore:** inverse edit (`if False:` back to `if added is not False:`).
- **Restore receipt** (read back by the Grep tool, `if added is not False`):

```
260:        if added is not False:
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.56s
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
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:269: in test_c5_a_target_that_is_not_a_worthless_test_finding_refuses
    _refused(_fold([_removed()], _target(**change)), "C5")
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:99: in _refused
    assert outcome["discharged"] == [] and outcome["notDischarged"] == ["t0"]
E   AssertionError: assert (['t0'] == []
E     
E     Left contains one more item: 't0'
E     Use -v to get more diff)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_c5_a_target_that_is_not_a_worthless_test_finding_refuses[wrong-dimension]
1 failed in 0.51s
exit=1
```

- **Restore:** inverse edit (`if False:` back to `if finding.get("dimension") != "Test":`).
- **Restore receipt** (read back by the Grep tool, `dimension"\) != "Test"`):

```
202:    if finding.get("dimension") != "Test":
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.54s
exit=0
```

## G7. C6, one of the target's own cited lines lies in a removed range (`audits.test_removal_clearance`)

- **Axis:** a removal holding none of the target's own cited lines clears nothing; this entry proves the line-outside-every-range input (grouping above).
- **Detector:** `test_audit_test_removal_2434.py::test_c6_a_removal_holding_none_of_the_targets_lines_refuses`.
- **Neutralization:** `if not any(_inside(own, path, rng) for path, ranges, _a in rows for rng in ranges):` became `if False:`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_c6_a_removal_holding_none_of_the_targets_lines_refuses __________
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:277: in test_c6_a_removal_holding_none_of_the_targets_lines_refuses
    _refused(_fold([_removed()], _target(line=30)), "C6")
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:104: in _refused
    assert entry["reason"].startswith(prefix), entry["reason"]
E   AssertionError: audit check failed: testWouldFail: worthless-test-removed clears only a fix that removes test lines a worthless-test finding cites; C7: plugins/superheroes/lib/tests/test_widget_2434.py lines 10-14 hold no cited line
E   assert False
E    +  where False = <built-in method startswith of str object at 0x103cd5240>('audit check failed: testWouldFail: worthless-test-removed clears only a fix that removes test lines a worthless-test finding cites; C6: ')
E    +    where <built-in method startswith of str object at 0x103cd5240> = 'audit check failed: testWouldFail: worthless-test-removed clears only a fix that removes test lines a worthless-test finding cites; C7: plugins/superheroes/lib/tests/test_widget_2434.py lines 10-14 hold no cited line'.startswith
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_c6_a_removal_holding_none_of_the_targets_lines_refuses
1 failed in 0.50s
exit=1
```

- **Restore:** inverse edit (`if False:` back to the `any(...)` test).
- **Restore receipt** (read back by the Grep tool, `if not any\(_inside\(own`):

```
280:    if not any(_inside(own, path, rng) for path, ranges, _a in rows for rng in ranges):
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.57s
exit=0
```

## G8. C7, every removed range holds a cited line (`audits.test_removal_clearance`)

- **Axis:** a removed range that holds no line cited by the target or a worthless-smell sibling clears nothing, so the fix cannot also delete an uncited test; this entry proves the extra-range input (grouping above).
- **Detector:** `test_audit_test_removal_2434.py::test_c7_a_removed_range_holding_no_cited_line_refuses`.
- **Neutralization:** `if not _inside(cited, path, rng):` became `if False:`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_c7_a_removed_range_holding_no_cited_line_refuses _____________
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:309: in test_c7_a_removed_range_holding_no_cited_line_refuses
    reason = _refused(_fold([_removed()], _target(record=_two_ranges())), "C7")
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:99: in _refused
    assert outcome["discharged"] == [] and outcome["notDischarged"] == ["t0"]
E   AssertionError: assert (['t0'] == []
E     
E     Left contains one more item: 't0'
E     Use -v to get more diff)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_c7_a_removed_range_holding_no_cited_line_refuses
1 failed in 0.53s
exit=1
```

- **Restore:** inverse edit (`if False:` back to `if not _inside(cited, path, rng):`).
- **Restore receipt** (read back by the Grep tool, `if not _inside\(cited`):

```
285:            if not _inside(cited, path, rng):
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.50s
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
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:530: in test_r_a_replacement_and_a_new_file_mark_their_files_as_added_to
    assert _files(_removal(repo, base, head)) == {TFILE: ([[2, 2]], True), "tests/test_new.py": ([], True)}
E   AssertionError: assert {'tests/test_...: ([], False)} == {'tests/test_...': ([], True)}
E     
E     Differing items:
E     {'tests/test_a.py': ([[2, 2]], False)} != {'tests/test_a.py': ([[2, 2]], True)}
E     {'tests/test_new.py': ([], False)} != {'tests/test_new.py': ([], True)}
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_r_a_replacement_and_a_new_file_mark_their_files_as_added_to
1 failed in 1.27s
exit=1
```

- **Restore:** inverse edit (`if False:` back to `if new_count > 0:`).
- **Restore receipt** (read back by the Grep tool, `if new_count > 0`):

```
7017:            if new_count > 0:
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.17s
exit=0
```

## G10. The unreadable detection (`round_driver._fixer_removal`)

- **Axis:** a binary file in the diff makes the whole record unreadable; this entry proves the real-binary-file input (grouping above).
- **Detector:** `test_audit_test_removal_2434.py::test_r_a_binary_file_makes_the_whole_record_unreadable`.
- **Neutralization:** `elif line.startswith("Binary files ") or line.startswith("GIT binary patch"):` became `elif False:`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_r_a_binary_file_makes_the_whole_record_unreadable ____________
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:541: in test_r_a_binary_file_makes_the_whole_record_unreadable
    assert "unreadable" in record and "files" not in record
E   AssertionError: assert ('unreadable' in {'base': 'e530c083f63f6ba02d411d22a9d1faecf6ee11dd', 'head': 'bd6a5b18b0e81861d633472813bb59b51b1682bf', 'files': [{'path': 'tests/blob.bin', 'removed': [], 'added': False}, {'path': 'tests/test_a.py', 'removed': [[2, 8]], 'added': False}]})
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_r_a_binary_file_makes_the_whole_record_unreadable
1 failed in 1.17s
exit=1
```

- **Restore:** inverse edit (`elif False:` back to the two `startswith` tests).
- **Restore receipt** (read back by the Grep tool, `elif line.startswith\("Binary files `):

```
7004:        elif line.startswith("Binary files ") or line.startswith("GIT binary patch"):
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.19s
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
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:627: in test_r_a_configured_textconv_never_hides_an_added_line
    assert _files(_removal(repo, base, head)) == {"tests/test_a.txt": ([], True)}
E   AssertionError: assert {} == {'tests/test_...': ([], True)}
E     
E     Right contains 1 more item:
E     {'tests/test_a.txt': ([], True)}
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_r_a_configured_textconv_never_hides_an_added_line
1 failed in 1.44s
exit=1
```

- **Restore:** inverse edit (the argument put back).
- **Restore receipt** (read back by the Grep tool, `"--no-ext-diff", "--no-textconv", "--no-color", "--src-prefix=a/",`):

```
6985:    raw = _git_bytes(repo_root, "diff", "--no-ext-diff", "--no-textconv", "--no-color", "--src-prefix=a/",
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.43s
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
<worktree>/plugins/superheroes/lib/tests/test_audit_test_removal_2434.py:641: in test_r_the_record_describes_the_explicit_head_not_the_checkout
    assert _files(record) == {TFILE: ([], True)}
E   AssertionError: assert {'tests/test_..., 1]], False)} == {'tests/test_...': ([], True)}
E     
E     Differing items:
E     {'tests/test_a.py': ([[1, 1]], False)} != {'tests/test_a.py': ([], True)}
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_test_removal_2434.py::test_r_the_record_describes_the_explicit_head_not_the_checkout
1 failed in 1.51s
exit=1
```

- **Restore:** inverse edit (`"HEAD")` back to `shas[1])`).
- **Restore receipt** (read back by the Grep tool, `"--unified=0", shas\[0\]`):

```
6986:                     "--dst-prefix=b/", "--no-renames", "--unified=0", shas[0], shas[1])
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.97s
exit=0
```
</content>
