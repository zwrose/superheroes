# Bite-proof record: WO-1 of issue #2612 (the cloud check reads back which plugin copy each start part loaded)

Detector: `plugins/superheroes/lib/tests/test_cloud_check_start_parts_2612.py::test_a_one_part_from_an_older_copy_fails_and_names_it_and_the_marker_records_start` (one node).
Guarded element (declared by the order): the comparison `copy["sha256"] != want` in `cloud_check._start_match`. Axis: a start part whose loaded bytes differ from this machine's copy of it fails the check on `start`.
Neutralized by a targeted edit in production code only, the detector run alone as one test node id (no `-n`), then restored by the inverse edit (an edit, never a checkout/restore/reset/stash). The red was produced with the detector unedited.

Run command, each time, from the worktree root, as one plain command:
`scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc-2612 -m pytest "<node>" -q -p no:cacheprovider --tb=short`.
No output was filtered. Redaction: none needed (no secrets, tokens or personal data in the captures).

## 1. The comparison `copy["sha256"] != want`

- Neutralization (`cloud_check.py:661`, `_start_match`): `differing.extend((part, copy) for copy in value[part] if copy["sha256"] != want)` became `differing.extend((part, copy) for copy in value[part] if False and copy["sha256"] != want)`, so `differing` stays empty and the match reads True.
- Node: `plugins/superheroes/lib/tests/test_cloud_check_start_parts_2612.py::test_a_one_part_from_an_older_copy_fails_and_names_it_and_the_marker_records_start`.
- Red (on axis: the report names `lib/core_md.py` from plugin 0.40.0 with other bytes, and the judgment says `passed`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_one_part_from_an_older_copy_fails_and_names_it_and_the_marker_records_start _
/Users/zwrose/.superheroes-worktrees/superheroes/issue-2612-a7702606ea0115b8/plugins/superheroes/lib/tests/test_cloud_check_start_parts_2612.py:189: in test_a_one_part_from_an_older_copy_fails_and_names_it_and_the_marker_records_start
    assert result["action"] == "failed" and "start" in result["failedParts"]
E   AssertionError: assert ('passed' == 'failed'
E     
E     - failed
E     + passed)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check_start_parts_2612.py::test_a_one_part_from_an_older_copy_fails_and_names_it_and_the_marker_records_start
1 failed in 9.11s
```

- Restore: the inverse edit, removing `False and `. Restored text, `cloud_check.py:661`: `        differing.extend((part, copy) for copy in value[part] if copy["sha256"] != want)`
- Green:

```
.                                                                        [100%]
1 passed in 11.05s
```
