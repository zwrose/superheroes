# Bite-proof record: WO-B2 (#2040), the readers of the plugin pin (`cloud_ready`, `cloud_check`, `cloud_setup_text`, `launch_report`)

Declared guarded-element set (from the order): G1, G2, G3, G4, G5, G6, G7, G8, G9. One neutralization and one red
each, applied to the production code with the detectors unedited, each reverted by the inverse edit. Every run was
`scripts/pinned-python -B -X pycache_prefix=<scratchpad>/pyc -m pytest "<node id>" -q -p no:cacheprovider` from the
worktree, selected by exact node id (never `-k`). Production code was at `aee5b8a5`; the detectors are the tests
this order added. Nothing in the captures needed redaction. Captures are trimmed to the decisive lines: the
`UV_NATIVE_TLS` deprecation warning, the `tmp_path`/fixture lines and the unchanged test-body echo are elided. Each
restore receipt is the restored line quoted back from the file, plus an empty `git diff --stat` for the neutralized
file taken after the restore (the file is byte-identical to `aee5b8a5`).

## G1 — readiness rule (d): a broken pin is never read as absent

- **Guarded element and axis:** `cloud_ready.py:184-186` (`# axis: a broken pin hook is never read as absent`), the
  branch with no reported version: `pluginPin` is false when the pin state is `broken`.
- **Detector:** `plugins/superheroes/lib/tests/test_cloud_ready.py::test_rule_d_a_broken_pin_is_not_current_and_is_not_read_as_absent`
- **Neutralization (line 186):** `conditions["pluginPin"] = pin_state != "broken"` became `conditions["pluginPin"] = True`.
- **Raw red:**
  ```
  >       _only_false(got, "pluginPin")
  >       assert result["conditions"] == expected
  E       AssertionError: assert {'setup': Tru...n': True, ...} == {'setup': Tru...n': True, ...}
  E         Differing items:
  E         {'pluginPin': True} != {'pluginPin': False}
  FAILED plugins/superheroes/lib/tests/test_cloud_ready.py::test_rule_d_a_broken_pin_is_not_current_and_is_not_read_as_absent
  1 failed in 1.17s
  ```
  The red is on the claimed axis: a broken pin read as current.
- **Restore:** the inverse edit, `True` back to `pin_state != "broken"`.
- **Restore receipt (line 186 quoted back):** `        conditions["pluginPin"] = pin_state != "broken"`; `git diff --stat -- cloud_ready.py` empty.
- **Raw green:** `1 passed in 1.45s`

## G2 — readiness rule (c): the pin is current only when its version is the advisor's

- **Guarded element and axis:** `cloud_ready.py:180` (`# axis: with a valid pin the cloud runs the pinned version once
  the session starts`), the valid-pin branch: `pluginPin` is true only when `pin_version == advisor`.
- **Detector:** `plugins/superheroes/lib/tests/test_cloud_ready.py::test_rule_c_a_valid_pin_naming_another_version_is_not_current`
- **Neutralization (line 180):** `conditions["pluginPin"] = advisor is not None and pin_version == advisor` became
  `conditions["pluginPin"] = True`.
- **Raw red:**
  ```
  >       _only_false(got, "pluginPin")
  E       AssertionError: assert {'setup': Tru...n': True, ...} == {'setup': Tru...n': True, ...}
  E         Differing items:
  E         {'pluginPin': True} != {'pluginPin': False}
  FAILED plugins/superheroes/lib/tests/test_cloud_ready.py::test_rule_c_a_valid_pin_naming_another_version_is_not_current
  1 failed in 1.41s
  ```
  The red is on the claimed axis: a pin naming 1.2.2 read as current for an advisor at 1.2.3.
- **Restore:** the inverse edit, `True` back to `advisor is not None and pin_version == advisor`.
- **Restore receipt (line 180 quoted back):** `        conditions["pluginPin"] = advisor is not None and pin_version == advisor`; `git diff --stat -- cloud_ready.py` empty.
- **Raw green:** `1 passed in 0.57s`

## G3 — readiness rule (a): the pin never overrides a reported version

- **Guarded element and axis:** `cloud_ready.py:171-172` (`# axis: a reported version stands alone; the pin never
  overrides it`), the reported-version branch taken ahead of the pin branch.
- **Detector:** `plugins/superheroes/lib/tests/test_cloud_ready.py::test_rule_a_a_reported_version_decides_and_the_pin_never_overrides_it`
- **Neutralization (line 171):** `if reported.get("pluginVersion") is not None:` became
  `if reported.get("pluginVersion") is not None and pin_state != "valid":`, so a valid pin takes the branch instead.
- **Raw red:**
  ```
  >       _only_false(stale, "version")
  E       AssertionError: assert {'setup': Tru...n': True, ...} == {'setup': Tru...': False, ...}
  E         Differing items:
  E         {'version': True} != {'version': False}
  FAILED plugins/superheroes/lib/tests/test_cloud_ready.py::test_rule_a_a_reported_version_decides_and_the_pin_never_overrides_it
  1 failed in 0.75s
  ```
  The red is on the claimed axis: a cloud that reported 1.2.2 read as current because the pin names the advisor's version.
- **Restore:** the inverse edit, removing ` and pin_state != "valid"`.
- **Restore receipt (line 171 quoted back):** `    if reported.get("pluginVersion") is not None:`; `git diff --stat -- cloud_ready.py` empty.
- **Raw green:** `1 passed in 0.91s`

## G4 — judge: the reported commit must equal the pin's commit

- **Guarded element and axis:** `cloud_check.py:485-488` (`# axis: the cloud must run the commit the pin names, and
  the pin must name the plugin this machine runs`), the commit leg.
- **Detector:** `plugins/superheroes/lib/tests/test_cloud_check.py::test_judge_fails_the_pin_part_when_the_cloud_runs_another_commit`
- **Neutralization (line 487):** the line `                  and obj["pluginCommit"] == pin["pin"]["commit"]` was removed.
  The version leg on the next line was left in place.
- **Raw red:**
  ```
  >       assert result["action"] == "failed" and result["failedParts"] == ["pin"]
  E       AssertionError: assert ('passed' == 'failed'
  E         - failed
  E         + passed)
  FAILED plugins/superheroes/lib/tests/test_cloud_check.py::test_judge_fails_the_pin_part_when_the_cloud_runs_another_commit
  1 failed in 1.24s
  ```
  The red is on the claimed axis: a cloud reporting commit `bbbb...` passed a project pinned to another commit.
- **Restore:** the inverse edit, putting the removed line back.
- **Restore receipt (lines 486-488 quoted back):**
  ```
          pin_ok = (isinstance(obj.get("pluginCommit"), str)
                    and obj["pluginCommit"] == pin["pin"]["commit"]
                    and pin["pin"]["version"] == local_version)
  ```
  `git diff --stat -- cloud_check.py` empty.
- **Raw green:** `1 passed in 1.21s`

## G5 — setup text: a broken state is refused, never composed

- **Guarded element and axis:** `cloud_setup_text.py:898` (`# axis: a broken pin hook is refused, never composed as
  absent or valid`), the refusal in `_compose`.
- **Detector:** `plugins/superheroes/lib/tests/test_cloud_setup_text.py::test_a_broken_hook_is_refused_by_the_text_and_the_stamp_readers`
- **Neutralization (line 898):** `if state["state"] == "broken":  # axis: ...` became
  `if False and state["state"] == "broken":  # axis: ...`. The matching refusal in `stamped_files` (line 597) was left in place.
- **Raw red:**
  ```
  >           _refusal(_compose(w), "plugin-pin-broken")
  >       assert result["action"] == "refused" and result["reason"] == reason, result
  E       AssertionError: {'action': 'written', 'reason': None, 'text': '#!/bin/bash\n# Corner Shop · plugin 0.45.0 · calibration from 10 Oct\n#...
  E       assert ('written' == 'refused'
  E         - refused
  E         + written)
  FAILED plugins/superheroes/lib/tests/test_cloud_setup_text.py::test_a_broken_hook_is_refused_by_the_text_and_the_stamp_readers
  1 failed in 0.58s
  ```
  The red is on the claimed axis: a broken hook composed as an absent one (the header carries no pin note).
- **Restore:** the inverse edit, removing `False and `.
- **Restore receipt (line 898 quoted back):** `    if state["state"] == "broken":  # axis: a broken pin hook is refused, never composed as absent or valid`; `git diff --stat -- cloud_setup_text.py` empty.
- **Raw green:** `1 passed in 0.70s`

## G6 — the `setup-steps` stamp entry

- **Guarded element and axis:** `cloud_setup_text.py:562` (`_pin_view`, the `SETUP_STEPS_STAMP_KEY` entry); the stamp
  covers the setup text's fixed install and fetch steps, which a pin commit cannot move.
- **Detector:** `plugins/superheroes/lib/tests/test_cloud_setup_text.py::test_the_stamp_changes_when_a_tool_step_of_the_setup_text_changes`
- **Neutralization (lines 562-563):** the `return {SETUP_STEPS_STAMP_KEY: (...), SETUP_INVENTORY_STAMP_KEY: ...}` became
  `return {SETUP_INVENTORY_STAMP_KEY: _plugin_inventory()}`.
- **Raw red:**
  ```
  >       assert _real_stamp(w) != before
  E       AssertionError: assert 'sha256:7255c84a7aec3f499831450a389e0286b5c61cd5f21b42fd53ec35b89d8d3f26' != 'sha256:7255c84a7aec3f499831450a389e0286b5c61cd5f21b42fd53ec35b89d8d3f26'
  FAILED plugins/superheroes/lib/tests/test_cloud_setup_text.py::test_the_stamp_changes_when_a_tool_step_of_the_setup_text_changes
  1 failed in 0.75s
  ```
  The red is on the claimed axis: a changed reviewer-tool package left the stamp unchanged.
- **Restore:** the inverse edit, putting the `SETUP_STEPS_STAMP_KEY` entry back.
- **Restore receipt (lines 562-563 quoted back):**
  ```
      return {SETUP_STEPS_STAMP_KEY: ("\n".join(steps) + "\n").encode("utf-8"),
              SETUP_INVENTORY_STAMP_KEY: _plugin_inventory()}
  ```
  `git diff --stat -- cloud_setup_text.py` empty.
- **Raw green:** `1 passed in 0.65s`

## G7 — the `setup-plugin-inventory` stamp entry

- **Guarded element and axis:** `cloud_setup_text.py:563` (`_pin_view`, the `SETUP_INVENTORY_STAMP_KEY` entry); the stamp
  covers the plugin parts a cloud session loads at its start, before the pin hook can swap the plugin.
- **Detector:** `plugins/superheroes/lib/tests/test_cloud_setup_text.py::test_the_stamp_changes_when_an_agent_file_changes`
- **Neutralization (lines 562-563):** the return became `return {SETUP_STEPS_STAMP_KEY: ("\n".join(steps) + "\n").encode("utf-8")}`.
- **Raw red:**
  ```
  >       assert _real_stamp(w) != before
  E       AssertionError: assert 'sha256:b0a61023712ba09826414c402b7fa12013639d7a11075fbdc9f779d45392b35f' != 'sha256:b0a61023712ba09826414c402b7fa12013639d7a11075fbdc9f779d45392b35f'
  FAILED plugins/superheroes/lib/tests/test_cloud_setup_text.py::test_the_stamp_changes_when_an_agent_file_changes
  1 failed in 0.63s
  ```
  The red is on the claimed axis: a changed agent file left the stamp unchanged.
- **Restore:** the inverse edit, putting the `SETUP_INVENTORY_STAMP_KEY` entry back.
- **Restore receipt (lines 562-563 quoted back):** the same two lines as G6's receipt; `git diff --stat -- cloud_setup_text.py` empty.
- **Raw green:** `1 passed in 0.56s`

## G8 — the I1 gate: no pin entries for an absent hook

- **Guarded element and axis:** `cloud_setup_text.py:577-579` (`# axis: only a valid pin hook adds these two entries,
  so a project without one keeps its stamp`), the gate in `_view_for`.
- **Detector:** `plugins/superheroes/lib/tests/test_cloud_setup_text.py::test_a_project_without_the_hook_has_no_pin_entries_in_its_stamp`
- **Neutralization (line 578):** `if pin_on:` became `if True:`, so `stamped_files` adds the two entries for every project.
- **Raw red:**
  ```
  >       assert not set(PIN_KEYS) & set(CS.stamped_files(w.cwd, w.root))
  E       assert not ({'setup-plugin-inventory', 'setup-steps'} & {'config/core.md', 'config/review-crew.md', 'doc-policy.json', 'meta.json', 'permission/rules.json', 'registry.json', ...})
  FAILED plugins/superheroes/lib/tests/test_cloud_setup_text.py::test_a_project_without_the_hook_has_no_pin_entries_in_its_stamp
  1 failed in 0.59s
  ```
  The red is on the claimed axis: both entries appeared in the stamp of a project with no hook files.
- **Restore:** the inverse edit, `True` back to `pin_on`.
- **Restore receipt (line 578 quoted back):** `    if pin_on:`; `git diff --stat -- cloud_setup_text.py` empty.
- **Raw green:** `1 passed in 0.60s`. This is a re-run of the same node id on the restored code, made after the record was
  drafted because the original green capture was not reliably kept (one extra invocation outside the 18).

## G9 — launch_report: `pluginPin` in `_REREAD_REASONS`

- **Guarded element and axis:** `launch_report.py:32` (`_REREAD_REASONS`); a plugin-pin fallback clears when readiness
  re-reads `pluginPin` true, with no later check.
- **Detector:** `plugins/superheroes/lib/tests/test_launch_report.py::test_a_plugin_pin_fallback_clears_when_readiness_reads_the_pin_current_again`
- **Neutralization (line 32):** `"pluginPin", ` was removed from the tuple of condition names.
- **Raw red:**
  ```
  >       assert LR._fixed(candidate, fixed) is True
  E       AssertionError: assert False is True
  E        +  where False = <function _fixed at 0x7f4ee5553100>({'reason': 'plugin-pin', 'by': 'setting', 'cloudVersion': None, 'advisorVersion': None, ...}, {'ready': False, 'reason': 'plugin-pin', 'conditions': {'setup': True, 'passPresent': True, 'passLive': True, 'version': True, ...}, 'setting': True, ...})
  FAILED plugins/superheroes/lib/tests/test_launch_report.py::test_a_plugin_pin_fallback_clears_when_readiness_reads_the_pin_current_again
  1 failed in 0.31s
  ```
  The red is on the claimed axis: with `pluginPin` true the fallback still stood.
- **Restore:** the inverse edit, putting `"pluginPin", ` back between `"passLive", ` and `"dependencyHook", `.
- **Restore receipt (line 32 quoted back):** `_REREAD_REASONS = tuple(cloud_ready.REASON_FOR[name] for name in ("setup", "passLive", "pluginPin", "dependencyHook", "calibration"))`; `git diff --stat -- launch_report.py` empty.
- **Raw green:** `1 passed in 0.27s`

## After the last restore

`git diff -- plugins/superheroes/lib/*.py` is empty (exit 0): the production code is byte-identical to `aee5b8a5`.
