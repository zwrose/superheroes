# C11 layer 3b (#1270) bite-proof — the vet-244 fold and the 2c craft follow-ups

**Provenance:** WO-F (`conformance_probe.py`, `launcher.py`, `engine_dispatch.py` — implementer cursor composer-2.5, maker family xai) and the carried WO-B/WO-B2 hunks (`payload_contracts.py`, `engine_dispatch.py`, `round_driver.py` — cursor composer-2.5, xai). All elements re-run by the orchestrator on the final code head `cb09a7fc` in a detached probe worktree.

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| F-a1 | `_validate_probe_record` ok-vs-legs check | ok-vs-legs consistency refuses | `test_preflight_entry_refuses_ok_disagreeing_with_legs` |
| F-a2 | `_validate_probe_record` failed-list check | failed-list consistency refuses | `test_preflight_entry_refuses_failed_list_disagreeing_with_legs` |
| F-a3 | `preflight_entry` absent-wave arm under `wave=` | absent wave under --wave refuses | `test_preflight_entry_refuses_record_without_wave_under_wave` |
| F-b1 | `probe()` given-run-dir prompt name | given run dir: prompt is a run-dir-named sibling | `test_probe_prompt_lands_beside_a_given_run_dir` |
| F-b2 | `probe()` private parent when no run dir | no run dir: private parent holds prompt and run dir | `test_probe_without_run_dir_uses_a_private_parent` |
| F-c1 | `_effective_last_activity` (no seam arm) | probe telemetry read has no seam arm | `test_grade_legs_rejects_injected_seam_record_without_stamp` |
| F-c2 | injected-seam `attempt-ended` record stamps `lastActivityAt` | injected-seam record stamps lastActivityAt | `test_probe_injected_seam_stamps_last_activity_at` |
| F-d1 | `_expected_probe_cell` reads `model_registry.matrix_config` | _expected_probe_cell reads model_registry | `test_expected_probe_cell_reads_the_registry_home` |
| F-e/G7 | `walk_preflight` fail branch carries `checks` (entry built once) | walk_preflight fail branch carries checks (entry built once) | `test_walk_preflight_failed_check_carries_checks` |
| F-f2 | `walk_preflight` appends the failing entry after every earlier pass | later-walked failure carries every earlier pass | `test_walk_preflight_later_walked_failure_carries_every_earlier_pass` |
| F-f3a | `preflight_entry` stale bound is `>`, not `>=` | stale boundary: age == max_age passes | `test_preflight_entry_stale_boundary_exact_age_passes` |
| F-f3b | `preflight_entry` negative age refuses | stale boundary: negative age refuses | `test_preflight_entry_stale_boundary_future_completed_at_refuses` |
| F-f4 | `_parse_completed_at` naive-timestamp guard | naive completedAt refuses, never raises | `test_preflight_entry_completed_at_parse_edges[naive]` |
| B1 | `payload_contracts._check_scalar_type` `non-empty-string` branch | top-level blank scalar refusal | `test_top_level_non_empty_string_refuses_blank_scalar` |
| B2 | `payload_contracts._check_element_fields` per-field `non-empty-string` block | element blank refusal (sole site after collapse) | `test_payload_contracts_non_empty_string_rejects_blank` |
| B3 | `engine_dispatch._journal_read_raw` `isinstance(rec, dict)` guard | non-object JSON journal line typed as corruption | `test_journal_line_valid_json_not_object_is_typed_corruption` |
| B3' | `_journal_read_raw` per-call `corruption_class_set` | corruption class does not leak between reads | `test_journal_corruption_class_does_not_leak_between_reads` |
| B4 | `round_driver._loop_verifier_artifact_faults` list arm | verifier faults in one round accumulate | `test_two_verifier_faults_in_one_round_are_both_recorded` |

## Method

Detached worktree pinned at `cb09a7fc`, `git status --porcelain` empty before the first element and after every restore. Per element: exact-string mutation through a file edit (`count(old) == 1` asserted before the write, the whole file rewritten only by that one substitution), the named test selected by its exact node id (never `-k`), red captured, the inverse substitution, green captured. Red is the runner's own exit code (`1`), green is `0`. Tails below are the last pytest lines, not reconstructed. The B family re-proves WO-B's B1–B3 and WO-B2's B3' (first proved on the layer-3 WO-B/WO-B2 heads, `bd77f830` / `09cc1984`) and adds B4 for the verifier-fault accumulation that had a test but no recorded proof.


### F-a1 — ok-vs-legs consistency refuses

- **site:** `plugins/superheroes/lib/conformance_probe.py`
- **neutralization:** replace `    if raw.get("ok") != computed_ok:` with `    if False:`
- **raw red:** `FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_preflight_entry_refuses_ok_disagreeing_with_legs` — `E       assert 0 == 1`
- **restore:** inverse replace (tree clean: `git status --porcelain` empty = True)
- **raw green:** `1 passed in 0.17s`
- **verdict:** RED->GREEN

### F-a2 — failed-list consistency refuses

- **site:** `plugins/superheroes/lib/conformance_probe.py`
- **neutralization:** replace `    if not isinstance(failed, list) or sorted(failed) != sorted(computed_failed):` with `    if False:`
- **raw red:** `FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_preflight_entry_refuses_failed_list_disagreeing_with_legs` — `E       assert 0 == 1`
- **restore:** inverse replace (tree clean: `git status --porcelain` empty = True)
- **raw green:** `1 passed in 0.16s`
- **verdict:** RED->GREEN

### F-a3 — absent wave under --wave refuses

- **site:** `plugins/superheroes/lib/conformance_probe.py`
- **neutralization:** replace `            if not result_wave or result_wave != wave:` with `            if result_wave and result_wave != wave:`
- **raw red:** `FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_preflight_entry_refuses_record_without_wave_under_wave` — `E       assert 0 == 1`
- **restore:** inverse replace (tree clean: `git status --porcelain` empty = True)
- **raw green:** `1 passed in 0.16s`
- **verdict:** RED->GREEN

### F-b1 — given run dir: prompt is a run-dir-named sibling

- **site:** `plugins/superheroes/lib/conformance_probe.py`
- **neutralization:** replace `            os.path.basename(run_dir_real) + ".probe-prompt.md",` with `            "probe-prompt.md",`
- **raw red:** `FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_probe_prompt_lands_beside_a_given_run_dir` — `E       AssertionError: assert False`
- **restore:** inverse replace (tree clean: `git status --porcelain` empty = True)
- **raw green:** `1 passed in 0.20s`
- **verdict:** RED->GREEN

### F-b2 — no run dir: private parent holds prompt and run dir

- **site:** `plugins/superheroes/lib/conformance_probe.py`
- **neutralization:** replace `            run_dir = os.path.join(parent, "run")` with `            run_dir = parent`
- **raw red:** `FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_probe_without_run_dir_uses_a_private_parent` — `E       AssertionError: assert '/private/var.../probe-parent' == '/private/var...be-parent/run'`
- **restore:** inverse replace (tree clean: `git status --porcelain` empty = True)
- **raw green:** `1 passed in 0.20s`
- **verdict:** RED->GREEN

### F-c1 — probe telemetry read has no seam arm

- **site:** `plugins/superheroes/lib/conformance_probe.py`
- **neutralization:** replace `    return ended.get("lastActivityAt")` with `    last_at = ended.get("lastActivityAt")\n    if last_at is not None:\n        return last_at\n    if ended.get("activitySource") == "injected-seam" and engagement.get("telemetry") == "tool-calls":\n        return ended.get("at")\n    return None`
- **raw red:** `FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_grade_legs_rejects_injected_seam_record_without_stamp` — `E       assert True is False`
- **restore:** inverse replace (tree clean: `git status --porcelain` empty = True)
- **raw green:** `1 passed in 0.16s`
- **verdict:** RED->GREEN

### F-c2 — injected-seam record stamps lastActivityAt

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **neutralization:** replace `        "lastActivityAt": ended_at,` with `        "lastActivityAt": None,`
- **raw red:** `FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_probe_injected_seam_stamps_last_activity_at` — `E       assert 1 == 0`
- **restore:** inverse replace (tree clean: `git status --porcelain` empty = True)
- **raw green:** `1 passed in 0.19s`
- **verdict:** RED->GREEN

### F-d1 — _expected_probe_cell reads model_registry

- **site:** `plugins/superheroes/lib/conformance_probe.py`
- **neutralization:** replace `    cell = model_registry.matrix_config(PROBE_ROLE, engine)` with `    cell = seat_map.matrix_config(PROBE_ROLE, engine)`
- **raw red:** `FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_expected_probe_cell_reads_the_registry_home` — `E       AssertionError: assert ['codex', 'm-y', 'e-y'] == ['codex', 'm-x', 'e-x']`
- **restore:** inverse replace (tree clean: `git status --porcelain` empty = True)
- **raw green:** `1 passed in 0.16s`
- **verdict:** RED->GREEN

### F-e/G7 — walk_preflight fail branch carries checks (entry built once)

- **site:** `plugins/superheroes/lib/launcher.py`
- **neutralization:** replace `            return _fail("preflight-failed:%s" % check_id, checks=out_checks)` with `            return _fail("preflight-failed:%s" % check_id)`
- **raw red:** `FAILED plugins/superheroes/lib/tests/test_launcher.py::test_walk_preflight_failed_check_carries_checks` — `E       AssertionError: assert 'checks' in {'ok': False, 'reason': 'preflight-failed:engine-auth'}`
- **restore:** inverse replace (tree clean: `git status --porcelain` empty = True)
- **raw green:** `1 passed in 0.34s`
- **verdict:** RED->GREEN

### F-f2 — later-walked failure carries every earlier pass

- **site:** `plugins/superheroes/lib/launcher.py`
- **neutralization:** replace `            out_checks.append(entry_out)\n            return _fail("preflight-failed:%s" % check_id, checks=out_checks)` with `            return _fail("preflight-failed:%s" % check_id, checks=out_checks)`
- **raw red:** `FAILED plugins/superheroes/lib/tests/test_launcher.py::test_walk_preflight_later_walked_failure_carries_every_earlier_pass` — `E       AssertionError: assert ['engine-auth...r-capability'] == ['engine-auth...ability', ...]`
- **restore:** inverse replace (tree clean: `git status --porcelain` empty = True)
- **raw green:** `1 passed in 0.34s`
- **verdict:** RED->GREEN

### F-f3a — stale boundary: age == max_age passes

- **site:** `plugins/superheroes/lib/conformance_probe.py`
- **neutralization:** replace `        if completed is None or age < 0 or age > max_age_seconds:` with `        if completed is None or age < 0 or age >= max_age_seconds:`
- **raw red:** `FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_preflight_entry_stale_boundary_exact_age_passes` — `E       assert 1 == 0`
- **restore:** inverse replace (tree clean: `git status --porcelain` empty = True)
- **raw green:** `1 passed in 0.17s`
- **verdict:** RED->GREEN

### F-f3b — stale boundary: negative age refuses

- **site:** `plugins/superheroes/lib/conformance_probe.py`
- **neutralization:** replace `        if completed is None or age < 0 or age > max_age_seconds:` with `        if completed is None or age > max_age_seconds:`
- **raw red:** `FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_preflight_entry_stale_boundary_future_completed_at_refuses` — `E       assert 0 == 1`
- **restore:** inverse replace (tree clean: `git status --porcelain` empty = True)
- **raw green:** `1 passed in 0.16s`
- **verdict:** RED->GREEN

### F-f4 — naive completedAt refuses, never raises

- **site:** `plugins/superheroes/lib/conformance_probe.py`
- **neutralization:** replace `    if parsed.tzinfo is None:\n        return None` with `(deleted)`
- **raw red:** `FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_preflight_entry_completed_at_parse_edges[2026-09-19T12:00:00-probe-stale:codex]` — `E           TypeError: can't subtract offset-naive and offset-aware datetimes`
- **restore:** inverse replace (tree clean: `git status --porcelain` empty = True)
- **raw green:** `1 passed in 0.16s`
- **verdict:** RED->GREEN

### B1 — top-level blank scalar refusal

- **site:** `plugins/superheroes/lib/payload_contracts.py`
- **neutralization:** replace `    elif type_token == "non-empty-string":\n        if not isinstance(value, str) or not value or value.strip() == "":` with `    elif type_token == "non-empty-string":\n        if False:`
- **raw red:** `FAILED plugins/superheroes/lib/tests/test_payload_contracts.py::test_top_level_non_empty_string_refuses_blank_scalar` — `E       assert None is not None`
- **restore:** inverse replace (tree clean: `git status --porcelain` empty = True)
- **raw green:** `1 passed in 0.05s`
- **verdict:** RED->GREEN

### B2 — element blank refusal (sole site after collapse)

- **site:** `plugins/superheroes/lib/payload_contracts.py`
- **neutralization:** replace `        if tok == "non-empty-string":\n            if not isinstance(value, str) or not value or value.strip() == "":` with `        if tok == "non-empty-string":\n            if False:`
- **raw red:** `FAILED plugins/superheroes/lib/tests/test_payload_contracts.py::test_payload_contracts_non_empty_string_rejects_blank` — `E       assert None is not None`
- **restore:** inverse replace (tree clean: `git status --porcelain` empty = True)
- **raw green:** `1 passed in 0.05s`
- **verdict:** RED->GREEN

### B3 — non-object JSON journal line typed as corruption

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **neutralization:** replace `        if not isinstance(rec, dict):\n            interior_corrupt = True\n            corruption_class_set.add(JOURNAL_LINE_NOT_OBJECT)\n            continue` with `(deleted)`
- **raw red:** `FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_journal_line_valid_json_not_object_is_typed_corruption` — `E       assert False is True`
- **restore:** inverse replace (tree clean: `git status --porcelain` empty = True)
- **raw green:** `1 passed in 0.72s`
- **verdict:** RED->GREEN

### B3' — corruption class does not leak between reads

- **site:** `plugins/superheroes/lib/engine_dispatch.py`
- **neutralization:** replace `    corruption_class_set = set()` with `    corruption_class_set = globals().setdefault("_leak_probe", set())`
- **raw red:** `FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_journal_corruption_class_does_not_leak_between_reads` — `E       AssertionError: assert ['journal-line-not-object'] == []`
- **restore:** inverse replace (tree clean: `git status --porcelain` empty = True)
- **raw green:** `1 passed in 0.67s`
- **verdict:** RED->GREEN

### B4 — verifier faults in one round accumulate

- **site:** `plugins/superheroes/lib/round_driver.py`
- **neutralization:** replace `        if isinstance(fault, list):\n            faults.extend(fault)\n        elif isinstance(fault, dict):` with `        if isinstance(fault, dict):`
- **raw red:** `FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_two_verifier_faults_in_one_round_are_both_recorded` — `E       assert 0 == 2`
- **restore:** inverse replace (tree clean: `git status --porcelain` empty = True)
- **raw green:** `1 passed in 0.59s`
- **verdict:** RED->GREEN

