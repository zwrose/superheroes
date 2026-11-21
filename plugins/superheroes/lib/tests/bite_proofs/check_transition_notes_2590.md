# Bite-proof: upgrade-note CI check (issue 2590, work order B)

Detector set declared by the order (8 elements, one entry each; no equivalence classes, nothing unproven):
1 the base-side read, 2 the `--release` branch, 3 the base-unresolvable edge, 4 the exit code, 5 the counted
removed-heading check in `compare_pr`, 6 / 7 / 8 the wiring of the three `ci.yml` steps (6: shape step `if:`,
7: no-direct-note step `if:`, 8: release step `--release` argument).

Method for every entry: the target text occurred exactly once (the Edit tool refuses a non-unique match),
one targeted edit, the exact test node id run with the detector unedited, the inverse edit, the same node id
run again. Runner: `scripts/pinned-python -B -X pycache_prefix=/tmp/wo-b-pyc -m pytest <node id> -q`.
Redaction: none needed (no secrets, tokens or URLs in the captures); the repeated
`warning: The UV_NATIVE_TLS ...` line from the pinned-python wrapper is elided from each capture below
(it is the same one line in every run).

Note on entry 1: a first neutralization of element 1 was run against the earlier single combined test
`test_assembly_passes_and_an_assembly_missing_its_section_is_refused`; it went red on the missing-section half
(`assert 0 == 1`, line 147), which masked the assembly-green half the order names. That test was restored,
split into `test_assembly_missing_its_section_is_refused_then_the_real_assembly_passes` and
`test_assembly_by_the_release_doc_pass_passes`, and the proof below was re-run on the split test.

## 1. Base-side read (`check_transition_notes.py`, the `tn.compare_pr(...)` call) - axis: the base's note files reach `compare_pr`, so an assembly reads as removal-with-assembly rather than a direct note

- Neutralization: `tn.compare_pr(base_transition, head_transition, base_notes, head_notes)` -> `tn.compare_pr(base_transition, head_transition, [], head_notes)`
- Red node: `.github/scripts/tests/test_check_transition_notes.py::test_assembly_by_the_release_doc_pass_passes`

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________ test_assembly_by_the_release_doc_pass_passes _________________
    def test_assembly_by_the_release_doc_pass_passes(tmp_path):
        repo, base = _make_repo(tmp_path, base_notes=[("7.md", NOTE_7)])
        assembled = _lib(repo).assemble(str(_plugin(repo)), "1.1.0")
        assert assembled["ok"] is True
        assert not os.path.exists(str(_notes_dir(repo) / "7.md"))
        code, result, err = _run(repo, "--base", base)
>       assert code == 0
E       assert 1 == 0
.github/scripts/tests/test_check_transition_notes.py:165: AssertionError
FAILED .github/scripts/tests/test_check_transition_notes.py::test_assembly_by_the_release_doc_pass_passes
1 failed in 0.30s
```
(traceback header lines `tmp_path = PosixPath(...)` and blank lines elided)

- Restore: inverse edit (`[]` -> `base_notes`). Restore receipt, line quoted back from the edit: `tn.compare_pr(base_transition, head_transition, base_notes, head_notes)`.
- Green: `. [100%]` / `1 passed in 0.43s`

## 2. `--release` branch (`if args.release:`) - axis: a note file still present on the release PR is refused

- Neutralization: `    if args.release:` -> `    if False:` (the `release_problems` call under it unchanged)
- Red node: `.github/scripts/tests/test_check_transition_notes.py::test_release_pr_refuses_an_unassembled_note_then_passes_after_assembly`

```
F                                                                        [100%]
    def test_release_pr_refuses_an_unassembled_note_then_passes_after_assembly(tmp_path):
        repo, base = _make_repo(tmp_path, base_notes=[("7.md", NOTE_7)])
        code, result, err = _run(repo, "--base", base, "--release")
>       assert code == 1
E       assert 0 == 1
.github/scripts/tests/test_check_transition_notes.py:174: AssertionError
FAILED .github/scripts/tests/test_check_transition_notes.py::test_release_pr_refuses_an_unassembled_note_then_passes_after_assembly
1 failed in 0.22s
```

- Restore: inverse edit (`if False:` -> `if args.release:`). Receipt: `    if args.release:` / `        problems.extend(tn.release_problems(head_notes))`.
- Green: `. [100%]` / `1 passed in 0.44s`

## 3. Base-unresolvable edge (`_read_base`, failed `rev-parse`) - axis: a base that cannot be resolved is refused with `base-unresolvable`, never read as an empty base

- Neutralization: `raise _BaseUnresolvable("The base " + sha + " is not a commit in this repository.")` -> `return "", []`
- Red node: `.github/scripts/tests/test_check_transition_notes.py::test_unresolvable_base_is_refused_then_a_real_base_passes`

```
F                                                                        [100%]
    def test_unresolvable_base_is_refused_then_a_real_base_passes(tmp_path):
        repo, base = _make_repo(tmp_path)
        code, result, err = _run(repo, "--base", ZERO_SHA)
        assert code == 1
        assert result["ok"] is False
>       assert _tokens(result) == ["base-unresolvable"]
E       AssertionError: assert ['transition-...bullet-added'] == ['base-unresolvable']
E         At index 0 diff: 'transition-heading-added' != 'base-unresolvable'
E         Left contains one more item: 'transition-bullet-added'
.github/scripts/tests/test_check_transition_notes.py:205: AssertionError
FAILED .github/scripts/tests/test_check_transition_notes.py::test_unresolvable_base_is_refused_then_a_real_base_passes
1 failed in 0.21s
```

- Restore: inverse edit. Receipt: `        raise _BaseUnresolvable("The base " + sha + " is not a commit in this repository.")`.
- Green: `. [100%]` / `1 passed in 0.42s`

## 4. Exit code (`return 0 if not problems else 1`) - axis: any problem makes the process exit 1

- Neutralization: `    return 0 if not problems else 1` -> `    return 0`
- Red node: `.github/scripts/tests/test_check_transition_notes.py::test_malformed_note_is_refused_then_fixed_passes`

```
F                                                                        [100%]
    def test_malformed_note_is_refused_then_fixed_passes(tmp_path):
        repo, _base = _make_repo(tmp_path)
        (_notes_dir(repo) / "8.md").write_text(NOTE_8_UNMARKED)
        code, result, err = _run(repo)
>       assert code == 1
E       assert 0 == 1
.github/scripts/tests/test_check_transition_notes.py:114: AssertionError
FAILED .github/scripts/tests/test_check_transition_notes.py::test_malformed_note_is_refused_then_fixed_passes
1 failed in 0.18s
```

- Restore: inverse edit. Receipt: `    return 0 if not problems else 1`.
- Green: `. [100%]` / `1 passed in 0.34s`

## 5. Counted removed-heading check (`transition_notes.py`, `compare_pr`) - axis: a removed note's heading is assembled only when the added-heading multiset covers it (heading count, not membership)

- Neutralization: `if uncovered[sec["heading"]] > 0:` -> `if sec["heading"] in head["headings"]:` (the old membership test, inverted to keep the branch shape)
- Red node: `plugins/superheroes/lib/tests/test_transition_notes.py::test_compare_removed_heading_already_at_base_must_be_added_again`
- Axis check: the fixture's bullet delta equals the removed bullets, so the bullet check is silent; the red is the heading check returning `[]` where one `note-removed-unassembled` is owed.

```
F                                                                        [100%]
>       assert tokens(problems) == ["note-removed-unassembled"]
E       AssertionError: assert [] == ['note-removed-unassembled']
E         Right contains one more item: 'note-removed-unassembled'
/home/user/wt-2590-b/plugins/superheroes/lib/tests/test_transition_notes.py:629: AssertionError
FAILED plugins/superheroes/lib/tests/test_transition_notes.py::test_compare_removed_heading_already_at_base_must_be_added_again
1 failed in 0.29s
```
(the test body echoed in the traceback is elided; it is the test's own source)

- Restore: inverse edit. Receipt (`git diff` of the lib file after restore): `+            if uncovered[sec["heading"]] > 0:` / `+                uncovered[sec["heading"]] -= 1` / `+            else:`.
- Green: `. [100%]` / `1 passed in 0.28s`

## 6. Shape step `if:` in `ci.yml` - axis: the shape-only step runs off pull requests (push to main), never on a PR

- Neutralization: `if: github.event_name != 'pull_request'` -> `if: github.event_name == 'pull_request'` (that step only)
- Red node: `.github/scripts/tests/test_ci_workflow.py::test_note_shape_step_runs_off_pull_requests`

```
F                                                                        [100%]
>       assert step.get("if") == "github.event_name != 'pull_request'"
E       assert "github.event...pull_request'" == "github.event...pull_request'"
E         - github.event_name != 'pull_request'
E         + github.event_name == 'pull_request'
.github/scripts/tests/test_ci_workflow.py:161: AssertionError
FAILED .github/scripts/tests/test_ci_workflow.py::test_note_shape_step_runs_off_pull_requests
1 failed in 0.11s
```

- Restore: inverse edit, then `git diff -- .github/workflows/ci.yml` shows `+        if: github.event_name != 'pull_request'` under the shape step.
- Green: `. [100%]` / `1 passed in 0.08s`

## 7. No-direct-note step `if:` in `ci.yml` - axis: the base-comparison step runs on every pull request

- Neutralization: `if: github.event_name == 'pull_request'` -> `if: github.event_name != 'pull_request'` (the "no note straight into TRANSITION.md" step only)
- Red node: `.github/scripts/tests/test_ci_workflow.py::test_note_direct_step_runs_on_pull_requests_with_base`

```
F                                                                        [100%]
>       assert step.get("if") == "github.event_name == 'pull_request'"
E       assert "github.event...pull_request'" == "github.event...pull_request'"
E         - github.event_name == 'pull_request'
E         + github.event_name != 'pull_request'
.github/scripts/tests/test_ci_workflow.py:171: AssertionError
FAILED .github/scripts/tests/test_ci_workflow.py::test_note_direct_step_runs_on_pull_requests_with_base
1 failed in 0.10s
```

- Restore: inverse edit, then `git diff -- .github/workflows/ci.yml` shows `+        if: github.event_name == 'pull_request'` under that step.
- Green: `. [100%]` / `1 passed in 0.11s`

## 8. Release step `--release` argument in `ci.yml` - axis: the release-PR step passes `--release`

- Neutralization: `check_transition_notes.py --base "$BASE_SHA" --release` -> `check_transition_notes.py --base "$BASE_SHA"` (the release step only)
- Red node: `.github/scripts/tests/test_ci_workflow.py::test_note_release_step_runs_on_release_branch_with_release_flag`

```
F                                                                        [100%]
>       assert "--release" in run
E       assert '--release' in 'python3 .github/scripts/check_transition_notes.py --base "$BASE_SHA"'
.github/scripts/tests/test_ci_workflow.py:189: AssertionError
FAILED .github/scripts/tests/test_ci_workflow.py::test_note_release_step_runs_on_release_branch_with_release_flag
1 failed in 0.10s
```

- Restore: inverse edit, then `git diff -- .github/workflows/ci.yml` shows `+        run: python3 .github/scripts/check_transition_notes.py --base "$BASE_SHA" --release`.
- Green: `. [100%]` / `1 passed in 0.12s`

## Final run on the finished tree (after every restore)

`85 passed in 3.25s` for `.github/scripts/tests/test_check_transition_notes.py`, `.github/scripts/tests/test_ci_workflow.py`
and `plugins/superheroes/lib/tests/test_transition_notes.py`.
