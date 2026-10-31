# Bite-proof record: C8c WO-A (issue #1862)

> Note (2026-10-31, #2296): owner-machine paths and the name of a consuming project in this record were replaced with neutral placeholders after capture; nothing else changed.

Declared guarded-element set (the order's): A1, A2a, A2b, A2c, A2d, A3, A4 (plus A4's second test, separately neutralizable and run as A4b), A5, A6a, A6b, A6c, A6d, plus the A7 entries, which went to `c8_cloud_cleanup.md` entries 15-17 (the record the three `# axis:` comments name).

Every proof: the neutralization is one targeted edit; the detector is run alone as one node (a parametrized test counts as one node and runs all its cases); the restore is the inverse edit; the restore receipt quotes the restored line back; the green is the same node after the restore.

Command, each time, from the worktree root:
`scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest '<file>::<test>' -q -p no:cacheprovider --tb=short`

Pinned condition: none beyond the tests' own fixtures (a temporary git repository and a ledger root under `tmp_path`). The tests set no clock or git-config pin of their own.

Redaction: none needed; the captures hold only temporary paths under `/private/tmp/claude-501/pytest-of-zwrose/` and object addresses, left as printed. The parametrized reds (A6a, A6b, A6d) are the tail of the output; the cases listed are all the cases that ran.

All paths below are under `plugins/superheroes/lib/` and `plugins/superheroes/lib/tests/`.

## A1. A budget-skipped slug lookup leaves the cell unresolved

- Element and axis: `wave_watch.py:877` (`_slug_for_read`): the cell is filled only when a lookup ran (a slug, or a non-None refusal); a `(None, None)` budget skip leaves it `_SLUG_UNRESOLVED`.
- Detector: `test_wave_watch_builder_note.py::test_the_slug_lookup_skipped_for_a_spent_budget_is_resolved_by_a_later_reader`. Its companion `test_a_slug_lookup_that_failed_is_cached_and_a_later_reader_makes_no_second_call` guards edge (b) and passed in the final self-check; it is not the skip-axis detector and has no neutralization of its own here (it would go red only if a real failure stopped being cached, which this neutralization does not do).
- Neutralization: `if slug_cell is not None and (slug is not None or refusal_result is not None):` became `if slug_cell is not None:`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_the_slug_lookup_skipped_for_a_spent_budget_is_resolved_by_a_later_reader _
/path/to/home/.superheroes-worktrees/superheroes/issue-1862-c8c-wo-a/plugins/superheroes/lib/tests/test_wave_watch_builder_note.py:586: in test_the_slug_lookup_skipped_for_a_spent_budget_is_resolved_by_a_later_reader
    assert cell[0] is ww._SLUG_UNRESOLVED
E   assert None is <object object at 0x101eb1ca0>
E    +  where <object object at 0x101eb1ca0> = ww._SLUG_UNRESOLVED
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_builder_note.py::test_the_slug_lookup_skipped_for_a_spent_budget_is_resolved_by_a_later_reader
1 failed in 0.95s
```

- Restore: the inverse edit.
- Restore receipt: `877:    if slug_cell is not None and (slug is not None or refusal_result is not None):`
- Green:

```
.                                                                        [100%]
1 passed in 7.71s
```

## A2a. `_derive_batch_lanes` reads the ledger without creating it

- Element and axis: `wave_watch.py:481`, `ll.read(repo_root, env=env, create=False)`: a read-only arm makes no ledger root or repo-id directory.
- Detector: `test_wave_watch.py::test_run_on_an_absent_ledger_root_refuses_and_creates_no_directory`.
- Neutralization: `ll.read(repo_root, env=env, create=False)` became `ll.read(repo_root, env=env)`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_run_on_an_absent_ledger_root_refuses_and_creates_no_directory ______
/path/to/home/.superheroes-worktrees/superheroes/issue-1862-c8c-wo-a/plugins/superheroes/lib/tests/test_wave_watch.py:970: in test_run_on_an_absent_ledger_root_refuses_and_creates_no_directory
    assert not absent.exists()
E   AssertionError: assert not True
E    +  where True = exists()
E    +    where exists = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1613/test_run_on_an_absent_ledger_r0/absent-ledger-root').exists
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch.py::test_run_on_an_absent_ledger_root_refuses_and_creates_no_directory
1 failed in 0.90s
```

- Restore: the inverse edit.
- Restore receipt: `481:    read_result = ll.read(repo_root, env=env, create=False)`
- Green:

```
.                                                                        [100%]
1 passed in 0.66s
```

## A2b. `watch_arm` resolves the ledger path without creating it

- Element and axis: `wave_watch.py:2452`, `ll.ledger_path(repo_root, env=env, create=False)` in `watch_arm`: a read-only arm makes no ledger root.
- Detector: `test_wave_watch.py::test_watch_arm_on_an_absent_ledger_root_refuses_and_creates_no_directory`.
- Neutralization: `ledger_path_result = ll.ledger_path(repo_root, env=env, create=False)` became `ledger_path_result = ll.ledger_path(repo_root, env=env)` (the one in `watch_arm`, after the `REFUSAL_MAX_SECONDS_INVALID` check).
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_watch_arm_on_an_absent_ledger_root_refuses_and_creates_no_directory ___
/path/to/home/.superheroes-worktrees/superheroes/issue-1862-c8c-wo-a/plugins/superheroes/lib/tests/test_wave_watch.py:959: in test_watch_arm_on_an_absent_ledger_root_refuses_and_creates_no_directory
    assert not absent.exists()
E   AssertionError: assert not True
E    +  where True = exists()
E    +    where exists = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1615/test_watch_arm_on_an_absent_le0/absent-ledger-root').exists
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch.py::test_watch_arm_on_an_absent_ledger_root_refuses_and_creates_no_directory
1 failed in 1.07s
```

- Restore: the inverse edit.
- Restore receipt: `2452:        ledger_path_result = ll.ledger_path(repo_root, env=env, create=False)`
- Green:

```
.                                                                        [100%]
1 passed in 0.83s
```

## A2c. `run` resolves the ledger path without creating it

- Element and axis: `wave_watch.py:2558`, `ll.ledger_path(repo_root, env=env, create=False)` in `run`: a read-only run makes no ledger root.
- Detector: `test_wave_watch.py::test_run_on_an_absent_ledger_root_refuses_and_creates_no_directory`.
- Neutralization: the call in `run` (after the `ignore_refusal` block) became `ll.ledger_path(repo_root, env=env)`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_run_on_an_absent_ledger_root_refuses_and_creates_no_directory ______
/path/to/home/.superheroes-worktrees/superheroes/issue-1862-c8c-wo-a/plugins/superheroes/lib/tests/test_wave_watch.py:970: in test_run_on_an_absent_ledger_root_refuses_and_creates_no_directory
    assert not absent.exists()
E   AssertionError: assert not True
E    +  where True = exists()
E    +    where exists = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1617/test_run_on_an_absent_ledger_r0/absent-ledger-root').exists
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch.py::test_run_on_an_absent_ledger_root_refuses_and_creates_no_directory
1 failed in 0.91s
```

- Restore: the inverse edit.
- Restore receipt: `2558:        ledger_path_result = ll.ledger_path(repo_root, env=env, create=False)` (and `2452` unchanged, same text).
- Green:

```
.                                                                        [100%]
1 passed in 1.17s
```

Note on A2a and A2c: the run test goes red under either neutralization, as the tick that `run` makes reaches `_derive_batch_lanes`. The three sites are separately neutralizable and each was proved on its own; A2b is the only one the `watch_arm` test is the representative for.

## A2d. The note read does not create the ledger directory

- Element and axis: `wave_watch.py:1414`, `_answered_notes_path(repo_root, env, create=False)` in `_evaluate_builder_notes`: the builder-note read makes no ledger directory.
- Detector: `test_wave_watch_builder_note.py::test_the_note_read_on_an_absent_ledger_root_creates_no_directory`.
- Neutralization: `create=False` became `create=True` at that call.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_the_note_read_on_an_absent_ledger_root_creates_no_directory _______
/path/to/home/.superheroes-worktrees/superheroes/issue-1862-c8c-wo-a/plugins/superheroes/lib/tests/test_wave_watch_builder_note.py:626: in test_the_note_read_on_an_absent_ledger_root_creates_no_directory
    assert not absent.exists()
E   AssertionError: assert not True
E    +  where True = exists()
E    +    where exists = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1619/test_the_note_read_on_an_absen0/absent-ledger-root').exists
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_builder_note.py::test_the_note_read_on_an_absent_ledger_root_creates_no_directory
1 failed in 0.64s
```

- Restore: the inverse edit.
- Restore receipt: `1414:    path = _answered_notes_path(repo_root, env, create=False)` and `1443:        path = _answered_notes_path(repo_root, env, create=True)` (the writer, `note_answered`, unchanged).
- Green:

```
.                                                                        [100%]
1 passed in 0.58s
```

## A3. A header quoted mid-text is not this message's send

- Element and axis: `cloud_relay.py:320` (`_decide`): a send is this message's only when its header line is at the start of the text, leading whitespace aside.
- Detector: `test_cloud_relay.py::test_a_send_quoting_this_messages_header_mid_text_is_not_its_send`.
- Neutralization (a probe edit to `cloud_relay.py`): `if t.lstrip().startswith(header)]` became `if header in t]`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_a_send_quoting_this_messages_header_mid_text_is_not_its_send _______
/path/to/home/.superheroes-worktrees/superheroes/issue-1862-c8c-wo-a/plugins/superheroes/lib/tests/test_cloud_relay.py:372: in test_a_send_quoting_this_messages_header_mid_text_is_not_its_send
    assert out["delivered"] is False and out["reason"] == "relay-silent"
E   AssertionError: assert (False is False and 'relay-text-mismatch' == 'relay-silent'
E     
E     - relay-silent
E     + relay-text-mismatch)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_a_send_quoting_this_messages_header_mid_text_is_not_its_send
1 failed in 0.90s
```

- Restore: the inverse edit.
- Restore receipt: `320:    sends = [(t, i) for t, i in sends if t.lstrip().startswith(header)]`
- Green:

```
.                                                                        [100%]
1 passed in 0.51s
```

## A4a. The header's final colon is part of the match

- Element and axis: `cloud_relay.py:320`: the header line's last character (`:`) decides attribution; a send that opens with the header minus the colon is not this message's.
- Detector: `test_cloud_relay.py::test_a_send_opening_with_the_header_minus_its_colon_is_not_this_messages_send`.
- Neutralization (probe edit): `startswith(header)` became `startswith(header[:-1])`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_send_opening_with_the_header_minus_its_colon_is_not_this_messages_send _
/path/to/home/.superheroes-worktrees/superheroes/issue-1862-c8c-wo-a/plugins/superheroes/lib/tests/test_cloud_relay.py:384: in test_a_send_opening_with_the_header_minus_its_colon_is_not_this_messages_send
    assert out["delivered"] is False and out["reason"] == "relay-silent"
E   AssertionError: assert (False is False and 'relay-text-mismatch' == 'relay-silent'
E     
E     - relay-silent
E     + relay-text-mismatch)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_a_send_opening_with_the_header_minus_its_colon_is_not_this_messages_send
1 failed in 0.62s
```

- Restore: the inverse edit.
- Restore receipt: `320:    sends = [(t, i) for t, i in sends if t.lstrip().startswith(header)]`
- Green:

```
.                                                                        [100%]
1 passed in 0.60s
```

## A4b. A header line with more text after it is still attributed (a mismatch, never silent)

- Element and axis: `cloud_relay.py:320`: attribution is by the header as a prefix, not by the whole first line; a send whose first line is the header plus more text is attributed and is a mismatch.
- Detector: `test_cloud_relay.py::test_a_send_whose_header_line_carries_more_text_is_attributed_and_a_mismatch`.
- Why a separate neutralization: the A4a neutralization (`header[:-1]`) still attributes this send, so the second test cannot tell it from the original; it is not red under A4a (not run under A4a; it follows from the code, and is the reason for this entry). The failure mode here is the opposite one, an attribution that is too strict.
- Neutralization (probe edit): `t.lstrip().startswith(header)` became `t.lstrip().split("\n", 1)[0] == header` (a send is attributed only when its first line equals the header).
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_send_whose_header_line_carries_more_text_is_attributed_and_a_mismatch _
/path/to/home/.superheroes-worktrees/superheroes/issue-1862-c8c-wo-a/plugins/superheroes/lib/tests/test_cloud_relay.py:395: in test_a_send_whose_header_line_carries_more_text_is_attributed_and_a_mismatch
    assert out["delivered"] is False and out["reason"] == "relay-text-mismatch"
E   AssertionError: assert (False is False and 'relay-silent' == 'relay-text-mismatch'
E     
E     - relay-text-mismatch
E     + relay-silent)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_a_send_whose_header_line_carries_more_text_is_attributed_and_a_mismatch
1 failed in 0.64s
```

- Restore: the inverse edit.
- Restore receipt: `320:    sends = [(t, i) for t, i in sends if t.lstrip().startswith(header)]`; `git status --porcelain plugins/superheroes/lib/cloud_relay.py` listed nothing.
- Green:

```
.                                                                        [100%]
1 passed in 0.62s
```

## A5. `cloud_setup.py` imports no `cloud_check`

- Element and axis: `cloud_setup.gardening_lines`: the gardening line uses `cloud_setup`'s own `FAILED_CHECK_SUFFIX`, `read_failed_check` and `_lapses_ok`, and imports no `cloud_check`, at any depth.
- Detector: `test_cloud_setup_gardening.py::test_cloud_setup_does_not_import_the_check_orchestrator`.
- Neutralization: `import cloud_check  # lazy: cloud_check imports this module` put back as the first line inside the `try:` of `gardening_lines`.
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_cloud_setup_does_not_import_the_check_orchestrator ____________
/path/to/home/.superheroes-worktrees/superheroes/issue-1862-c8c-wo-a/plugins/superheroes/lib/tests/test_cloud_setup_gardening.py:267: in test_cloud_setup_does_not_import_the_check_orchestrator
    assert "cloud_check" not in imported, imported
E   AssertionError: ['argparse', 'datetime', 'hashlib', 'json', 'os', 're', ...]
E   assert 'cloud_check' not in ['argparse', 'datetime', 'hashlib', 'json', 'os', 're', ...]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_setup_gardening.py::test_cloud_setup_does_not_import_the_check_orchestrator
1 failed in 0.19s
```

- Restore: the inverse edit (the line removed).
- Restore receipt: `grep -n "import cloud_check" cloud_setup.py` printed nothing; lines 420-423 read `    try:` / `        names = sorted(n for n in os.listdir(directory)` / `                       if n.endswith(".json") and not n.endswith(FAILED_CHECK_SUFFIX))` / `    except FileNotFoundError:`.
- Green:

```
.                                                                        [100%]
1 passed in 0.18s
```

## A6a. The account read from a record file is validated before use

- Element and axis: `cloud_setup.py:439` (`gardening_lines`): `_id_ok(found)` runs before the account builds a marker path or reads a record; an invalid one gives the unreadable line with account `None` and no marker read.
- Detector: `test_cloud_setup_gardening.py::test_a_record_file_with_an_invalid_account_is_unreadable_and_reads_no_marker` (7 cases: `""`, `5`, `None`, `["a"]`, `"has space"`, `"-leading"`, a 129-character string).
- Neutralization: `if not _id_ok(found):` became `if False and not _id_ok(found):`.
- Red (an abbreviated capture, labelled as such: the implementer shortened the long lines by hand, so this is not verbatim; the verbatim output was 7 failures, `7 failed in 16.95s`, and the orchestrator re-runs it):

```
FFFFFFF                                                                  [100%]
E     At index 0 diff: {'account': '', 'mark': None, 'line': 'Cloud reviewer pass: the setup record could not be read.'} != {'account': None, 'mark': None, 'line': 'Cloud reviewer pass: the setup record could not be read.'}
E     At index 0 diff: {'account': 5, 'mark': None, 'line': 'Cloud reviewer pass: the setup record could not be read.'} != {'account': None, ...
E   AssertionError: assert [('/private/t..._inv2/store')] == []        (case None: a marker read was attempted)
E     At index 0 diff: {'account': ['a'], ...
E     At index 0 diff: {'account': 'has space', ...
E     At index 0 diff: {'account': '-leading', ...
E     At index 0 diff: {'account': 'xxxx...', ...
7 failed in 16.95s
```

  (Elided: the pytest `FAILED` summary lines, one per case, and the 129-character account. The command was piped through `tail -60`, a filter, so a first line or two of the output is also not shown.)
- Restore: the inverse edit.
- Restore receipt: `439:            if not _id_ok(found):`
- Green:

```
.......                                                                  [100%]
7 passed in 4.00s
```

## A6b. A marker whose `failedParts` is not a list of strings is damaged

- Element and axis: `cloud_setup.py:448-449` (`gardening_lines`): `failedParts` must be a list of strings, else the marker reads as damaged (the "Renew now ... last reviewer check failed" line), never iterated as valid.
- Detector: `test_cloud_setup_gardening.py::test_a_marker_whose_failed_parts_is_not_a_list_of_strings_is_damaged` (6 cases: `"version"`, `{"reviewer": True}`, `5`, `["version", 3]`, `[3]`, `None`).
- Neutralization: the `well_formed = (isinstance(failed_parts, list) and all(isinstance(p, str) for p in failed_parts))` expression became `well_formed = True`.
- Red (an abbreviated capture, labelled as such: the `FAILED` summary paths are shortened to `...` by hand and the per-case tracebacks are condensed to one line; the verbatim output was `4 failed, 2 passed in 16.50s`. 4 of the 6 cases go red; the dict case still reaches the damaged line through `"reviewer" in failed_parts`, and `None` through `not failed_parts`, so those two pass under this neutralization):

```
F.FFF.                                                                   [100%]
E   AssertionError: assert (None == 'Renew now')     (cases: "version", 5, ["version", 3], [3])
FAILED ...::test_a_marker_whose_failed_parts_is_not_a_list_of_strings_is_damaged[version]
FAILED ...::test_a_marker_whose_failed_parts_is_not_a_list_of_strings_is_damaged[5]
FAILED ...::test_a_marker_whose_failed_parts_is_not_a_list_of_strings_is_damaged[parts3]
FAILED ...::test_a_marker_whose_failed_parts_is_not_a_list_of_strings_is_damaged[parts4]
4 failed, 2 passed in 16.50s
```

  (The summary's path prefix `plugins/superheroes/lib/tests/test_cloud_setup_gardening.py` is shortened to `...` here; it was printed in full.)
- Restore: the inverse edit.
- Restore receipt: `448:                well_formed = (isinstance(failed_parts, list)` / `449:                               and all(isinstance(p, str) for p in failed_parts))`
- Green:

```
......                                                                   [100%]
6 passed in 15.12s
```

## A6c. The switch-off state is reported: setting on is not called "off"

- Element and axis: `cloud_setup.py:408` (`_check_again`): `setting is False` is the only state the "stay off" sentence is used for; a setting that is on says cloud builds are still on and names the configure fix.
- Detector: `test_cloud_setup_gardening.py::test_with_the_setting_on_a_repair_line_says_cloud_builds_are_still_on` (siblings `test_with_the_setting_on_a_renew_line_says_...` and `test_a_setting_still_on_beside_a_marker_that_lost_its_setting_part_is_not_called_off`, the brief-check B2 end-to-end case, share this neutralization; they were not run alone under it).
- Neutralization: `if setting is False:` became `if True:` (always the "stay off" sentence).
- Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_with_the_setting_on_a_repair_line_says_cloud_builds_are_still_on _____
/path/to/home/.superheroes-worktrees/superheroes/issue-1862-c8c-wo-a/plugins/superheroes/lib/tests/test_cloud_setup_gardening.py:341: in test_with_the_setting_on_a_repair_line_says_cloud_builds_are_still_on
    assert got["line"] == "Cloud reviewer pass: the last cloud check failed on version. " + STILL_ON
E   AssertionError: assert 'Cloud review... check again.' == 'Cloud review... check again.'
E     
E     Skipping 49 identical leading characters in diff, use -v to show
E     - on version. Cloud builds are still on: I could not switch them off. Switch them off in configure, then run the setup check again.
E     + on version, so cloud builds stay off until a check passes. Run the setup check again.
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_setup_gardening.py::test_with_the_setting_on_a_repair_line_says_cloud_builds_are_still_on
1 failed in 5.17s
```

- Restore: the inverse edit.
- Restore receipt: `408:    if setting is False:` / `409:        return _CHECK_AGAIN, True`
- Green:

```
.                                                                        [100%]
1 passed in 5.38s
```

## A6d. An unreadable setting is claimed neither on nor off

- Element and axis: `cloud_setup.py:412` (`_check_again`, last return; the order's A6d named "treat the unreadable setting as off"): a setting that cannot be read (a raise, a refusal with no `effective`, a non-bool) gets a sentence that claims neither.
- Detector: `test_cloud_setup_gardening.py::test_an_unreadable_setting_is_claimed_neither_on_nor_off` (5 cases: a raise, a refusal, `{"effective": "yes"}`, `{"effective": None}`, a list).
- Neutralization: `return _SETTING_UNREAD, False` became `return _CHECK_AGAIN, True` (the unreadable setting treated as off).
- Red (all 5 cases fail; the command was piped through `tail -40`, a filter, so the first case's body is cut off and shown by its last line only, and the traces of answer2 to answer4 are condensed by hand to one note; the verbatim summary was `5 failed in 1.77s`):

```
E     + on version, so cloud builds stay off until a check passes. Run the setup check again.      (case answer0, last line only)
______ test_an_unreadable_setting_is_claimed_neither_on_nor_off[answer1] _______
/path/to/home/.superheroes-worktrees/superheroes/issue-1862-c8c-wo-a/plugins/superheroes/lib/tests/test_cloud_setup_gardening.py:381: in test_an_unreadable_setting_is_claimed_neither_on_nor_off
    assert got["line"] == ("Cloud reviewer pass: the last cloud check failed on version. "
E   AssertionError: assert 'Cloud review... check again.' == 'Cloud review... check again.'
E     
E     Skipping 49 identical leading characters in diff, use -v to show
E     - on version. I could not read whether cloud builds are on. Run the setup check again.
E     + on version, so cloud builds stay off until a check passes. Run the setup check again.
(answer2, answer3, answer4: the same four assertion lines)
FAILED plugins/superheroes/lib/tests/test_cloud_setup_gardening.py::test_an_unreadable_setting_is_claimed_neither_on_nor_off[answer0]
FAILED plugins/superheroes/lib/tests/test_cloud_setup_gardening.py::test_an_unreadable_setting_is_claimed_neither_on_nor_off[answer1]
FAILED plugins/superheroes/lib/tests/test_cloud_setup_gardening.py::test_an_unreadable_setting_is_claimed_neither_on_nor_off[answer2]
FAILED plugins/superheroes/lib/tests/test_cloud_setup_gardening.py::test_an_unreadable_setting_is_claimed_neither_on_nor_off[answer3]
FAILED plugins/superheroes/lib/tests/test_cloud_setup_gardening.py::test_an_unreadable_setting_is_claimed_neither_on_nor_off[answer4]
5 failed in 1.77s
```

- Restore: the inverse edit.
- Restore receipt: `412:    return _SETTING_UNREAD, False` (the last line of `_check_again`, after `if setting is True:` / `return STILL_ON_REPAIR + ", then run the setup check again.", False`).
- Green:

```
.....                                                                    [100%]
5 passed in 2.44s
```

## A7. See `c8_cloud_cleanup.md`, entries 15, 16, 17

The three `cloud_cleanup.py` axis comments (now ending `see bite-proof record c8_cloud_cleanup, entry 15 / 16 / 17`) point at the record that already named them; it had no entry for them and no other record holds them, so the entries were added there with red, restore and green run in this dispatch. Comments only in `cloud_cleanup.py`; no code line changed.
