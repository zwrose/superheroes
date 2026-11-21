# Bite-proof: WO-A (issue 2568), the setup stamp counts what a cloud session reads before the pin swap

Declared guarded-element set: G1 to G8 below. Each entry neutralizes production code with the
detector unedited (one exception, G3, disclosed in its entry), restores it by the inverse edit, and
shows the detector green again. Every run is a single node id:
`scripts/pinned-python -B -X pycache_prefix=<scratch>/pyc -m pytest <node id> -q -p no:cacheprovider`.
Captures are trimmed to the decisive lines (the `UV_NATIVE_TLS` deprecation warning line and the
full pytest source echo are elided); nothing in them needed redaction (no secret, token or
private URL appears).

## G1. `start_read_parts` counts the read-set files

- Element and axis: `cloud_setup_text.py` `start_read_parts`, `for rel in START_HOOK_READS:`;
  axis: a change to a read-set file moves the stamp.
- Detector: `plugins/superheroes/lib/tests/test_cloud_setup_text.py::test_the_stamp_moves_when_the_start_hook_changes`
- Neutralization: `for rel in START_HOOK_READS:` replaced by `for rel in ():`.
- Raw red:
  ```
  >       assert after != before
  E       AssertionError: assert 'sha256:85889f02e35316ef2f44f0d4d3f75e6e915eeba887d7bf61acdb19c7f1887c47' != 'sha256:85889f02e35316ef2f44f0d4d3f75e6e915eeba887d7bf61acdb19c7f1887c47'
  FAILED plugins/superheroes/lib/tests/test_cloud_setup_text.py::test_the_stamp_moves_when_the_start_hook_changes
  1 failed in 0.83s
  ```
- Restore: inverse edit (`for rel in ():` back to `for rel in START_HOOK_READS:`).
- Restore receipt: `cloud_setup_text.py:228:    for rel in START_HOOK_READS:`
- Raw green: `.  [100%]` / `1 passed in 5.00s`

## G2. `start_read_parts` counts only the `SessionStart` value

- Element and axis: `cloud_setup_text.py` `start_read_parts`, the `json.dumps(start, ...)` entry;
  axis: an edit to any other hooks-file key leaves the stamp unmoved.
- Detector: `plugins/superheroes/lib/tests/test_cloud_setup_text.py::test_the_stamp_does_not_move_for_a_part_read_after_the_pin_swap[pre_tool_use_entry]`
- Neutralization: the parsed-object entry replaced by `parts[hooks_key] = raw` (the whole file's bytes).
- Raw red:
  ```
  >       assert after == before
  E       AssertionError: assert 'sha256:b37ad...f2ba559e26039' == 'sha256:a5c72...ca9011fc5c1af'
  FAILED ...test_the_stamp_does_not_move_for_a_part_read_after_the_pin_swap[pre_tool_use_entry]
  1 failed in 4.51s
  ```
- Restore: inverse edit (`parts[hooks_key] = raw` back to the `json.dumps(...)` expression).
- Restore receipt (lines 223-224 of `cloud_setup_text.py` after the restore):
  ```
  parts[hooks_key] = json.dumps(
      start, sort_keys=True, ensure_ascii=False).encode("utf-8") + b"\n"
  ```
- Raw green: `.  [100%]` / `1 passed in 0.71s`

## G3. The `missing` marker for an absent read-set file

- Element and axis: `cloud_setup_text.py` `start_read_parts`, `parts[rel] = b"missing\n"`;
  axis: an absent read-set file is counted as the `missing` marker, so deleting one moves the stamp.
- Detector: `plugins/superheroes/lib/tests/test_cloud_setup_text.py::test_the_stamp_moves_when_a_read_set_file_is_deleted`
- Neutralization: `parts[rel] = b"missing\n"` replaced by `continue` (skip absent files).
- **Disclosure: the first red attempt was green, so the detector was edited before the proof stood.**
  With the detector as first written (it asserted only that the stamp moves), the neutralized code
  still passed: skipping the file drops its key from the inventory, which moves the stamp exactly as
  the marker does, so the stamp alone cannot tell the marker from an omission (`1 passed in 0.62s`,
  recorded here as the vacuous result). The fix was to the detector, not the assertion's strength:
  the deleted-file test now also asserts `CS.start_read_parts()["lib/git_origin.py"] == b"missing\n"`.
  The neutralization was restored, the detector edited, and the neutralization re-applied; the red
  below is from the final detector, which was not touched afterward.
- Raw red (final detector):
  ```
  >       assert CS.start_read_parts()["lib/git_origin.py"] == b"missing\n"
  E       KeyError: 'lib/git_origin.py'
  FAILED plugins/superheroes/lib/tests/test_cloud_setup_text.py::test_the_stamp_moves_when_a_read_set_file_is_deleted
  1 failed in 0.65s
  ```
- Restore: inverse edit (`continue` back to `parts[rel] = b"missing\n"`).
- Restore receipt (grep over the file): `232:            parts[rel] = b"missing\n"` and `235:            parts[rel] = _inventory_file(path)`
- Raw green: `.  [100%]` / `1 passed in 0.56s`

## G4. `START_HOOK_READS` is complete

- Element and axis: the `START_HOOK_READS` tuple; axis: every file the real hook opens in the
  plugin is listed.
- Detector: `plugins/superheroes/lib/tests/test_start_hook_read_set.py::test_the_listed_read_set_is_what_the_real_hook_reads`
- Neutralization: the line `    "lib/git_origin.py",` removed from the tuple.
- Raw red:
  ```
  E       AssertionError: read by the hook but not in START_HOOK_READS: ['lib/git_origin.py']
  E         in START_HOOK_READS but never read: []
  FAILED plugins/superheroes/lib/tests/test_start_hook_read_set.py::test_the_listed_read_set_is_what_the_real_hook_reads
  1 failed in 6.55s
  ```
- Restore: inverse edit (the line put back between `lib/core_md.py` and `lib/host_model.py`).
- Restore receipt: `69:    "lib/core_md.py",` / `70:    "lib/git_origin.py",` / `71:    "lib/host_model.py",`
- Raw green: `.  [100%]` / `1 passed in 6.17s`

## G5. `START_HOOK_READS` has no stale entry

- Element and axis: the `START_HOOK_READS` tuple; axis: every listed file is one the real hook opens.
- Detector: `plugins/superheroes/lib/tests/test_start_hook_read_set.py::test_the_listed_read_set_is_what_the_real_hook_reads`
- Neutralization: the line `    "lib/cloud_check.py",` added to the tuple (sorted position, after `lib/charter_detect.py`).
- Raw red:
  ```
  E       AssertionError: read by the hook but not in START_HOOK_READS: []
  E         in START_HOOK_READS but never read: ['lib/cloud_check.py']
  FAILED plugins/superheroes/lib/tests/test_start_hook_read_set.py::test_the_listed_read_set_is_what_the_real_hook_reads
  1 failed in 6.13s
  ```
- Restore: inverse edit (the line removed).
- Restore receipt: grep for `cloud_check|"lib/charter_detect.py"|"lib/cloud_pass.py"` in the file
  answers `64:    "lib/charter_detect.py",` and `65:    "lib/cloud_pass.py",` only (no `cloud_check` line).
- Raw green: `.  [100%]` / `1 passed in 6.56s`

## G6. `adopt_version` definition-change flag

- Element and axis: `adopt_version.py` `_cloud_start`, `definition_changed`; axis: two trees that
  count different things in the stamp are reported as a definition change, and that alone makes
  `setupSteps` true.
- Detector: `plugins/superheroes/lib/tests/test_adopt_version_cloud_start.py::test_a_new_stamp_definition_counts_even_with_identical_steps_and_parts`
- Neutralization: `... else pa["definition"] != pb["definition"]` replaced by `... else False`.
- Raw red:
  ```
  >       assert entry["stampDefinitionChanged"] is True
  E       assert False is True
  FAILED ...::test_a_new_stamp_definition_counts_even_with_identical_steps_and_parts
  1 failed in 0.45s
  ```
- Restore: inverse edit.
- Restore receipt: `271:        definition_changed = None if pa is None or pb is None else pa["definition"] != pb["definition"]`
- Raw green: `.  [100%]` / `1 passed in 0.51s`

## G7. `adopt_version` pin-state override

- Element and axis: `adopt_version.py` `_placed_stamp`, the `"1" if pin_valid else "0"` argument
  (and the `_STAMP_CODE` override it switches on); axis: a release's stamp is computed with the
  pin hook read as valid when the current reader finds it valid.
- Detector: `plugins/superheroes/lib/tests/test_adopt_version_cloud_start.py::test_a_release_reads_the_pin_hook_the_current_reader_finds_valid`
- Neutralization: `"1" if pin_valid else "0"` replaced by `"0"` (never pass `"1"`).
- Raw red:
  ```
  >       assert data["cloudStart"][0]["setupSteps"] is False
  E       assert None is False
  FAILED ...::test_a_release_reads_the_pin_hook_the_current_reader_finds_valid
  1 failed in 0.53s
  ```
- Restore: inverse edit.
- Restore receipt: `206:                               os.path.join(root, "lib"), project, "1" if pin_valid else "0"],`
- Raw green: `.  [100%]` / `1 passed in 0.43s`

## G8. `adopt_version` re-reads an older definition's inventory

- Element and axis: `adopt_version.py` `_effective_stamp`, the `placed["definition"] < STAMP_DEFINITION`
  branch; axis: a release counting an older definition is compared under the current one.
- Detector: `plugins/superheroes/lib/tests/test_adopt_version_cloud_start.py::test_an_older_definitions_inventory_is_re_read_under_the_current_one`
- Neutralization: `if placed["definition"] < ...` made `if False and placed["definition"] < ...`
  (always use the tree's own `stamp`).
- Raw red:
  ```
  >       assert entry["setupSteps"] is False
  E       assert True is False
  FAILED ...::test_an_older_definitions_inventory_is_re_read_under_the_current_one
  1 failed in 0.46s
  ```
- Restore: inverse edit.
- Restore receipt: `234:    if placed["definition"] < cloud_setup_text.STAMP_DEFINITION and view is not None and key in view:`
- Raw green: `.  [100%]` / `1 passed in 0.41s`
