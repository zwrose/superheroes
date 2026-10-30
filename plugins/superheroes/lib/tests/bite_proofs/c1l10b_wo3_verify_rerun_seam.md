# C1-L10b (WO-3) bite-proof — one home for "the same code" across a verify re-run

**Provenance:** implementer WO-3 / `lib/review_record.py`, `lib/round_driver.py`, `lib/pr_body_stage.py`, `lib/tests/test_c1l10b_verify_rerun_seam.py`

Declared guarded elements (from the order): E1 the review record's reading of the driver's `decision`; E2 the untracked half of `_verify_run_tree`; E3 the verb's recording of `treeSha`; E4 the footer strip on the PATCH read-back. Each was neutralized with one targeted edit, run alone against its named detector, and restored with the inverse edit (never `git checkout`, `restore`, `reset` or `stash`); the same command then ran green. Every run was `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -n auto --tb=line -p no:cacheprovider <nodes>` from the worktree root. The captures were not filtered except that the launcher's one-line `UV_NATIVE_TLS` deprecation warning was dropped (`grep -v UV_NATIVE`). They hold no secrets, tokens, private URLs or PII; the only paths are pytest's own.

| ID | Guarded element | Axis | Proving tests (all in `test_c1l10b_verify_rerun_seam.py`) |
|---|---|---|---|
| E1 | `review_record.py` `_decision`, read by `_rerun_line` and `_rerun_clause` | the line says "on unchanged code" only for a `went-on` decision | `test_1a_…`, `test_1b_…`, `test_1c_…` |
| E2 | `round_driver.py` `_verify_run_tree`, the `for raw in sorted(… untracked paths …)` half | an untracked file that is not ignored is working-tree contents | `test_an_untracked_file_added_between_the_runs_halts_a_passing_re_run`, `test_a_first_run_that_creates_an_untracked_file_and_fails_halts_a_passing_re_run`, `test_an_untracked_file_changes_the_digest_and_its_bytes_count` |
| E3 | `round_driver.py` `_run_verify_execute`, `payload["treeSha"] = tree_before` | the verb records the digest, so a tracked edit between the runs halts a passing re-run | `test_3_a_tracked_file_edited_between_the_runs_halts_a_passing_re_run_and_the_landing_carries_tree_sha` |
| E4 | `pr_body_stage.py` `_publish`, `strip_cloud_footer` on each side of the read-back comparison | a footer the cloud egress appends to a PATCHed body is not a difference | `test_4_a_footer_the_cloud_appends_to_the_patched_body_is_not_a_difference` |

The tree-digest halt and its recording are E2 (what the digest covers) and E3 (that the landing carries it); the halt itself (`verify-rerun-tree-changed` from two unequal digests) was proven by the earlier record `c1l9a_wo1_verify_rerun` and is exercised again, end to end, by the E2 and E3 detectors.

Not separately neutralized, so unproven by this record: the `decision` computation in `_fold_verify` (only its consumers are neutralized; the tests `test_the_driver_records_its_decision_on_the_entry_and_the_validator_accepts_it` and `test_the_decision_on_a_non_pass_second_result_is_failed_whatever_the_heads` assert it but were not run against a mutation), the `decision` and `heads` checks in `_rerun_fault`, the symlink and directory-marker branches of `_verify_run_tree`, and the `None` returns of `_verify_run_tree` on a failed git call or an unreadable file.

---

## E1 — the record's reading of the decision

**neutralization** (`review_record.py`, `_decision`, first line of the body; every entry reads as `went-on`):
```python
+    return "went-on"  # BITE-PROOF NEUTRALIZED
     decision = c.get("decision") if isinstance(c, dict) else None
```

**raw red:** the command above with the three nodes `…::test_1a_a_re_run_that_starts_at_another_head_and_ends_at_the_first_heads_halts_and_is_not_unchanged_code`, `…::test_1b_a_re_run_halted_on_changed_contents_is_not_unchanged_code_and_names_the_changed_contents` and `…::test_1c_only_a_decision_of_went_on_reads_as_unchanged_code`
```
bringing up nodes...
bringing up nodes...

FFF                                                                      [100%]
=================================== FAILURES ===================================
[gw1] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmptCmKdM/bin/python
E   AssertionError: assert ('unchanged code' not in 'Re-run afte... then passed'
      
      'unchanged code' is contained here:
        Re-run after one failure on unchanged code: round 1 `verify`: failed (exit 1) then passed
      ?                             ++++++++++++++)
/home/user/wt-2264/plugins/superheroes/lib/tests/test_c1l10b_verify_rerun_seam.py:116: AssertionError: assert ('unchanged code' not in 'Re-run afte... then passed'
[gw2] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmptCmKdM/bin/python
E   AssertionError: ('head-moved', 'Re-run after one failure on unchanged code: round 1 `verify`: failed (exit 1) then passed', 'Re-run after one failure on unchanged code: 1 checks (listed in the full record).')
    assert True == ('head-moved' == 'went-on'
      
      - went-on
      + head-moved)
/home/user/wt-2264/plugins/superheroes/lib/tests/test_c1l10b_verify_rerun_seam.py:125: AssertionError: ('head-moved', 'Re-run after one failure on unchanged code: round 1 `verify`: failed (exit 1) then passed', 'Re-run after one failure on unchanged code: 1 checks (listed in the full record).')
[gw0] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmptCmKdM/bin/python
E   AssertionError: assert ('on unchanged code' not in 'Re-run afte... then passed'
      
      'on unchanged code' is contained here:
        Re-run after one failure on unchanged code: round 1 `verify`: failed (exit 1) then passed
      ?                          +++++++++++++++++)
/home/user/wt-2264/plugins/superheroes/lib/tests/test_c1l10b_verify_rerun_seam.py:106: AssertionError: assert ('on unchanged code' not in 'Re-run afte... then passed'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l10b_verify_rerun_seam.py::test_1b_a_re_run_halted_on_changed_contents_is_not_unchanged_code_and_names_the_changed_contents
FAILED plugins/superheroes/lib/tests/test_c1l10b_verify_rerun_seam.py::test_1c_only_a_decision_of_went_on_reads_as_unchanged_code
FAILED plugins/superheroes/lib/tests/test_c1l10b_verify_rerun_seam.py::test_1a_a_re_run_that_starts_at_another_head_and_ends_at_the_first_heads_halts_and_is_not_unchanged_code
3 failed in 0.91s
```

**restore:** the inverse edit, removing the added `return "went-on"  # BITE-PROOF NEUTRALIZED` line.

**restore receipt:** the restored lines, as `grep -n "def _decision" -A5 plugins/superheroes/lib/review_record.py` printed them, and a search of `review_record.py` for `BITE-PROOF` (no match):
```
1822:def _decision(c):
1823-    """The driver's recorded decision on a verify re-run entry, or None when the entry has none (a record an
1824-    earlier version wrote) or a value that is not one of `RERUN_DECISIONS`. The record never works it out again."""
1825-    decision = c.get("decision") if isinstance(c, dict) else None
1826-    return decision if isinstance(decision, str) and decision in RERUN_DECISIONS else None
```

**raw green:** same command.
```
bringing up nodes...
bringing up nodes...

...                                                                      [100%]
3 passed in 0.78s
```

---

## E2 — the untracked half of the working-tree digest

**neutralization** (`round_driver.py`, `_verify_run_tree`; the loop over the untracked paths sees none):
```python
-    for raw in sorted(p for p in outputs[1].split(b"\0") if p):
+    for raw in sorted(p for p in outputs[1].split(b"\0") if p and False):  # BITE-PROOF NEUTRALIZED: if p
```

**raw red:** the command above with the three nodes `…::test_an_untracked_file_added_between_the_runs_halts_a_passing_re_run`, `…::test_a_first_run_that_creates_an_untracked_file_and_fails_halts_a_passing_re_run` and `…::test_an_untracked_file_changes_the_digest_and_its_bytes_count`
```
bringing up nodes...
bringing up nodes...

FFF                                                                      [100%]
=================================== FAILURES ===================================
[gw0] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpeqn64n/bin/python
E   AssertionError: assert 1 == 3
     +  where 1 = len({'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'})
/home/user/wt-2264/plugins/superheroes/lib/tests/test_c1l10b_verify_rerun_seam.py:214: AssertionError: assert 1 == 3
[gw3] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpeqn64n/bin/python
E   KeyError: 'treeShaAfter'
/home/user/wt-2264/plugins/superheroes/lib/tests/test_c1l10b_verify_rerun_seam.py:361: KeyError: 'treeShaAfter'
[gw1] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpeqn64n/bin/python
E   AssertionError: assert 'handed-back' == 'halted'
      
      - halted
      + handed-back
/home/user/wt-2264/plugins/superheroes/lib/tests/test_c1l10b_verify_rerun_seam.py:346: AssertionError: assert 'handed-back' == 'halted'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l10b_verify_rerun_seam.py::test_an_untracked_file_changes_the_digest_and_its_bytes_count
FAILED plugins/superheroes/lib/tests/test_c1l10b_verify_rerun_seam.py::test_a_first_run_that_creates_an_untracked_file_and_fails_halts_a_passing_re_run
FAILED plugins/superheroes/lib/tests/test_c1l10b_verify_rerun_seam.py::test_an_untracked_file_added_between_the_runs_halts_a_passing_re_run
3 failed in 4.37s
```
(`e3b0c442…` is the SHA-256 of the empty diff: with the untracked half skipped, a clean tree and a tree with new untracked files digest alike. In the end-to-end case the round goes on, ending `handed-back` rather than `halted`.)

**restore:** the inverse edit, back to `    for raw in sorted(p for p in outputs[1].split(b"\0") if p):`.

**restore receipt:** `grep -n "for raw in sorted" plugins/superheroes/lib/round_driver.py` printed `13917:    for raw in sorted(p for p in outputs[1].split(b"\0") if p):`, and `grep -c "BITE-PROOF" plugins/superheroes/lib/round_driver.py` printed `0`.

**raw green:** same command.
```
bringing up nodes...
bringing up nodes...

...                                                                      [100%]
3 passed in 2.42s
```

---

## E3 — the verb records `treeSha`

**neutralization** (`round_driver.py`, `_run_verify_execute`):
```python
-        payload["treeSha"] = tree_before
+        pass  # BITE-PROOF NEUTRALIZED: payload["treeSha"] = tree_before
```

**raw red:** the command above with `"…::test_3_a_tracked_file_edited_between_the_runs_halts_a_passing_re_run_and_the_landing_carries_tree_sha"`
```
bringing up nodes...
bringing up nodes...

F                                                                        [100%]
=================================== FAILURES ===================================
[gw0] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpijxmY8/bin/python
E   KeyError: 'treeSha'
/home/user/wt-2264/plugins/superheroes/lib/tests/test_c1l10b_verify_rerun_seam.py:403: KeyError: 'treeSha'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l10b_verify_rerun_seam.py::test_3_a_tracked_file_edited_between_the_runs_halts_a_passing_re_run_and_the_landing_carries_tree_sha
1 failed in 2.09s
```

**restore:** the inverse edit, back to `        payload["treeSha"] = tree_before`.

**restore receipt:** `grep -n 'payload\["treeSha"\]' -B1 -A1 plugins/superheroes/lib/round_driver.py` printed
```
13980-    if tree_before is not None:
13981:        payload["treeSha"] = tree_before
13982-        tree_after = _verify_run_tree(cwd)
```
and `BITE-PROOF` no longer appears in `round_driver.py`.

**raw green:** same command.
```
bringing up nodes...
bringing up nodes...

.                                                                        [100%]
1 passed in 2.21s
```

---

## E4 — the footer strip on the PATCH read-back

**neutralization** (`pr_body_stage.py`, `_publish`; the read-back is compared raw):
```python
-    if after is None or not _same_body(cloud_builder.strip_cloud_footer(after),
-                                       cloud_builder.strip_cloud_footer(staged)):
+    if after is None or not _same_body(after, staged):  # BITE-PROOF NEUTRALIZED: the strip_cloud_footer call on each side
```

**raw red:** the command above with `"…::test_4_a_footer_the_cloud_appends_to_the_patched_body_is_not_a_difference"`
```
bringing up nodes...
bringing up nodes...

F                                                                        [100%]
=================================== FAILURES ===================================
[gw0] linux -- Python 3.12.13 /root/.cache/uv/builds-v0/.tmpssmxfV/bin/python
E   AssertionError: assert (False, 'refu...h-unverified') == (True, 'published', None)
      
      At index 0 diff: False != True
      Use -v to get more diff
/home/user/wt-2264/plugins/superheroes/lib/tests/test_c1l10b_verify_rerun_seam.py:440: AssertionError: assert (False, 'refu...h-unverified') == (True, 'published', None)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l10b_verify_rerun_seam.py::test_4_a_footer_the_cloud_appends_to_the_patched_body_is_not_a_difference
1 failed in 0.82s
```

**restore:** the inverse edit, back to the two-line comparison with `cloud_builder.strip_cloud_footer(...)` on each side.

**restore receipt:** `sed -n 312,318p plugins/superheroes/lib/pr_body_stage.py` printed
```
        return done(OUTCOME_REFUSED, REASON_PUBLISH_FAILED)
    after = _read_live(runner, pr_text)
    # axis: a cloud session's egress appends its footer to a PATCHed body, so the read-back is compared without one footer — see bite-proof record c1l10b_wo3_verify_rerun_seam
    if after is None or not _same_body(cloud_builder.strip_cloud_footer(after),
                                       cloud_builder.strip_cloud_footer(staged)):
        return done(OUTCOME_REFUSED, REASON_PUBLISH_UNVERIFIED)
    return done(OUTCOME_PUBLISHED, None)
```
and a search of `plugins/superheroes/lib/*.py` for `BITE-PROOF` finds nothing.

**raw green:** same command.
```
bringing up nodes...
bringing up nodes...

.                                                                        [100%]
1 passed in 0.94s
```
