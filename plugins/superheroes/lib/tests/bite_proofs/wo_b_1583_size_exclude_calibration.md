# #1583 WO-B bite-proof — the `sizeExclude` calibration key

Bite-proof record for the `sizeExclude` key in `core.md`'s JSON block (`plugins/superheroes/lib/core_md.py`, `plugins/superheroes/lib/configure_view.py`), detectors in `plugins/superheroes/lib/tests/test_size_exclude_calibration_1583.py` (`T`).

**Declared guarded-element set (from the order): E1–E7.** One neutralization and one red per element, each a targeted Edit restored by the inverse Edit. Every red below is the single detector node run alone: `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest <node> -q`. Every green is the same command after the restore. Token literals are spelled as strings in the tests; `T::test_literal_pins` pins the constants.

**Status.** The implementer ran every proof (14 runs). Captures are quoted decisive-lines-only below; the full output of each run was printed in the dispatch session and is not stored on disk. Pytest's own `...Full output truncated` elision appeared in E5 and is reproduced as shown. The orchestrator re-runs proofs at verification.

## Per-element receipts

### E1 — not-a-list rule (refusal)

- **Neutralization.** `validate_size_exclude`: `if not isinstance(value, list):` became `if False and not isinstance(value, list):`.
- **Node.** `T::test_validate_not_a_list`
- **Red** (5 failed in 0.27s). First failing assertion, for `'docs/**'`:

```
E       AssertionError: assert 'size-exclude-entry-absolute' == 'size-exclude-not-a-list'
```

  `None`, `5`, `True` failed with `TypeError: '<type>' object is not iterable` out of the unguarded loop; `{'a': 1}` failed with `AssertionError: []` (`assert 0 == 1`).
- **Restore.** Inverse Edit; quoted back: `    if not isinstance(value, list):` then `        return [item(None, SIZE_EXCLUDE_MALFORMED_NOT_A_LIST, _SIZE_EXCLUDE_ACCEPTED_LIST)]`.
- **Green.** `5 passed in 0.46s`

### E2 — nonempty-string rule (refusal)

- **Neutralization.** `if not isinstance(entry, str) or not entry.strip():` became `if not isinstance(entry, str):`.
- **Node.** `T::test_validate_entry_empty_or_whitespace`
- **Red** (6 failed in 0.43s), every form `''`, `' '`, `'   '`, `'\t'`, `'\n'`, `' \t\n '`:

```
E       AssertionError: []
E       assert 0 == 1
```

- **Restore.** Inverse Edit; quoted back: `        if not isinstance(entry, str) or not entry.strip():`.
- **Green.** `6 passed in 0.14s`

### E3 — absolute rule (refusal)

- **Neutralization.** `elif entry.startswith("/"):` became `elif False and entry.startswith("/"):`.
- **Node.** `T::test_validate_entry_absolute`
- **Red** (4 failed in 0.16s), forms `'/'`, `'/docs/**'`, `'/abs/path'`, `'//x'`:

```
E       AssertionError: []
E       assert 0 == 1
```

- **Restore.** Inverse Edit; quoted back: `        elif entry.startswith("/"):`.
- **Green.** `4 passed in 0.13s`

### E4 — reader totality, the outer exception wrap (fail-closed read)

- **Neutralization.** `read_size_exclude`: `except Exception as exc:` became `except KeyboardInterrupt as exc:`.
- **Node.** `T::test_read_any_other_exception_is_total` (monkeypatches `_core_candidates`, a helper the reader calls, to raise `RuntimeError`).
- **Red** (1 failed in 0.75s):

```
E       RuntimeError: synthetic
/Users/zwrose/.superheroes-worktrees/superheroes/issue-1583-2a62b08ef9933a10/plugins/superheroes/lib/tests/test_size_exclude_calibration_1583.py:336: RuntimeError
```

- **Restore.** Inverse Edit; quoted back: `    except Exception as exc:  # total: any other failure is a named read refusal, never a raise`.
- **Green.** `1 passed in 0.73s`

### E5 — read-only path resolution (no write on read)

- **Neutralization.** `_size_exclude_core_path` gained `return core_path(cwd, root)` as its first statement, ahead of the candidate-existence logic.
- **Node.** `T::test_read_no_core_md_no_registry_writes_nothing` (hero evidence present, no registry, no core.md; asserts the store tree's file set is unchanged).
- **Red** (1 failed in 0.51s). The extra items are new store files:

```
E       AssertionError: assert {'/private/tm...ription', ...} == set()
E         Extra items in the left set:
E         '/private/tmp/claude-501/pytest-of-zwrose/pytest-167/test_read_no_core_md_no_regist0/store/projects/6d5c8a7b6c8ca477/.git'
E         '/private/tmp/claude-501/pytest-of-zwrose/pytest-167/test_read_no_core_md_no_regist0/store/projects/6d5c8a7b6c8ca477/registry.json'
E         '/private/tmp/claude-501/pytest-of-zwrose/pytest-167/test_read_no_core_md_no_regist0/store/projects/6d5c8a7b6c8ca477/.git/hooks'
```

- **Restore.** Inverse Edit; quoted back: `    in_repo, global_path = _core_candidates(cwd, root)` then `    in_exists = os.path.lexists(in_repo)`.
- **Green.** `1 passed in 0.31s`

### E6 — `confirm_all` carry site (preservation)

- **Neutralization.** `if SIZE_EXCLUDE_KEY in existing:` became `if False and SIZE_EXCLUDE_KEY in existing:`.
- **Node.** `T::test_carry_forward_confirm_all_keeps_key_byte_equal`
- **Red** (3 failed in 2.45s: `valid-unnormalized`, `malformed`, `not-a-list`):

```
E       KeyError: 'sizeExclude'
```

- **Restore.** Inverse Edit; quoted back: `            if SIZE_EXCLUDE_KEY in existing:`.
- **Green.** `3 passed in 2.41s`

### E7 — view render in the core-present branch (display)

- **Neutralization.** In `render`'s core-present branch, `for line in _size_exclude_view_lines(data.get("sizeExclude")):` became `for line in []:`. The core-absent branch was left intact.
- **Node.** `T::test_view_absent_key_shows_none_line`
- **Red** (1 failed in 2.20s). The failure is a `ValueError` from the test helper's `screen.index("### Size count exclusions")`, i.e. the heading line is missing from the screen:

```
E       ValueError: substring not found
```

- **Restore.** Inverse Edit; quoted back: `        for line in _size_exclude_view_lines(data.get("sizeExclude")):` followed by `            out.append(line)` and `        prefs = core.get("enginePreferences")`.
- **Green.** `1 passed in 2.06s`

### E8 — the path-free cause (display)

- **Neutralization.** In `_size_exclude_view_lines`, the `elif isinstance(payload.get("detail"), str):` branch body (`token = payload["detail"].split(":", 1)[0].strip()` / `if token:` / `lines.append("cause: %s" % token)`) became `lines.append(payload["detail"])`, so the reader's `detail` shows verbatim.
- **Node.** `test_configure_view.py::test_render_builder_dispatch_reason_shows_classifier_not_path`
- **Red** (1 failed in 2.85s):

```
>       assert core_md_path not in screen
E       AssertionError: assert '/private/tm...roes/core.md' not in '# superhero...ns\n(none)\n'
```

- **Restore.** Inverse Edit; quoted back: `            token = payload["detail"].split(":", 1)[0].strip()` then `            if token:` then `                lines.append("cause: %s" % token)`.
- **Green.** `1 passed in 2.71s`

## Notes the reader of the proof needs

- **Edge 9 premise.** The order names "cwd not a git repo" for the repo-root-unavailable edge. Measured on the pinned interpreter: a plain directory with no `.git` ancestor is greenfield (`store_core.repo_root` returns the cwd), so the reader reads `core-md-absent`. `RepoRootUnavailable` needs a `.git` entry that git declines. `T::test_read_repo_root_unavailable` uses an empty `.git` directory; `T::test_read_plain_non_git_dir_is_greenfield_core_absent` pins the plain-directory behaviour.
- **Axis of E5.** The red is on the no-write axis: new registry files in the store tree, not a changed `reason`.
