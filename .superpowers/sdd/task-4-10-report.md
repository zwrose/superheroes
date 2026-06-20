# Task 4–10 Implementation Report

## Functions in `.github/scripts/validate_skills.py`

- `check_line_count(skill_key, total_lines, ceilings) -> list[str]` — FR-3
- `check_links(skill_key, text, plugin_dir) -> list[str]` — FR-4
- `conventions_section_numbers(conventions_text) -> set[str]` — FR-4
- `check_conventions_refs(skill_key, text, conventions_sections) -> list[str]` — FR-4
- `check_toc(reference_path) -> list[str]` — FR-6
- `check_phrases(skill_key, description, required_phrases) -> list[str]` — FR-7
- `check_depth(skill_key, text, plugin_dir) -> list[str]` — FR-5
- `known_red_ceilings(baseline) -> set[str]` — FR-8
- `gather_violations(plugins_root, registry, red_set, conv_secs, combined_before=None) -> (errors, combined_now)` — FR-2/FR-10
- `main(argv=None) -> int` — UFR-1

Module-level constants: `REPO`, `PLUGINS`, `REGISTRY`, `BASELINE`, `CONVENTIONS`.

## Final `pytest .github/scripts/tests/test_validate_skills.py -q` output

```
..................                                                       [100%]
18 passed in 0.02s
```

## Local `validate_skills.py` exit code (pre-baseline)

Exit=1, sample output:
```
✗ 8 skill problem(s):
  - line-count: review-crew/audit-debt: 479 lines > ceiling 450
  - line-count: review-crew/review-code: 784 lines > ceiling 499
  - line-count: review-crew/review-plan: 544 lines > ceiling 499
  - line-count: review-crew/review-spec: 550 lines > ceiling 499
  - line-count: review-crew/review-tasks: 537 lines > ceiling 499
  - reference-link: workhorse/workhorse: unresolved reference lib
  - reference-link: workhorse/workhorse: unresolved reference lib
  - reference-link: workhorse/workhorse: unresolved reference lib/loop_state.py
```

This is expected pre-baseline (Task 14 records known-red and wires CI).

## Fix A + Fix B (false positive fixes — appended)

### Changed signature of `gather_violations`

```python
def gather_violations(plugins_root, registry, red_set, conv_secs, combined_before=None,
                      allowed_unresolved=frozenset()):
```

New parameter `allowed_unresolved` (keyword, default `frozenset()`) accepts a set of
`"<skill_key>:<relpath>"` strings. Any `reference-link` violation whose key+relpath is in
that set is silently suppressed. All existing positional call sites are unaffected.

### New tests added

- `test_links_accept_directory_target` — Fix A: a reference to an existing directory is NOT flagged.
- `test_links_allowlist_suppresses_sentinel` — Fix B part 1: a missing file IS flagged without allowlist.
- `test_gather_allowlist_suppresses_sentinel` — Fix B part 2: the violation IS suppressed when the `"<key>:<relpath>"` is in `allowed_unresolved`.

### pytest output after fixes

```
.....................                                                    [100%]
21 passed in 0.02s
```

### Validation output after fixes

The two bare `lib` directory false positives are GONE. `lib/loop_state.py` remains
(expected — Task 14 will add it to `allowedUnresolvedRefs` in baseline.json).

```
✗ 6 skill problem(s):
  - line-count: review-crew/audit-debt: 479 lines > ceiling 450
  - line-count: review-crew/review-code: 784 lines > ceiling 499
  - line-count: review-crew/review-plan: 544 lines > ceiling 499
  - line-count: review-crew/review-spec: 550 lines > ceiling 499
  - line-count: review-crew/review-tasks: 537 lines > ceiling 499
  - reference-link: workhorse/workhorse: unresolved reference lib/loop_state.py
```

### Commit hash

`d580763` — fix(ci): validate_skills check_links accepts dirs + baseline allowlist for deliberate sentinels

## Commit hashes (Tasks 4–10)

- Task 4: `d265057` — feat(ci): validate_skills line-count check (FR-3)
- Task 5: `ec1e5b0` — feat(ci): validate_skills reference + CONVENTIONS resolution (FR-4)
- Task 6: `bb4811d` — feat(ci): validate_skills one-level reference depth (FR-5)
- Task 7: `47e4ef2` — feat(ci): validate_skills TOC on long reference files (FR-6)
- Task 8: `0cb0a51` — feat(ci): validate_skills description trigger-phrase retention (FR-7)
- Task 9: `8994f34` — feat(ci): validate_skills main + known-red + combined-size + naming (FR-2/FR-10/UFR-1)
- Task 10: `08c0f42` — test(ci): validate_skills test suite resolves (CI step wired in Task 14)
