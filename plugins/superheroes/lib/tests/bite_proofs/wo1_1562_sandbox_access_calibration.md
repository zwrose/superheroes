# #1562 WO-1 bite-proof — the `sandboxAccess` calibration key

Bite-proof record for the `sandboxAccess` key in `core.md`'s JSON block (`plugins/superheroes/lib/core_md.py`, `plugins/superheroes/lib/configure_view.py`), detectors in `plugins/superheroes/lib/tests/test_sandbox_access_calibration_1562.py` (`T`).

**Status: the orchestrator ran every proof (G1–G8, G19, G20, G21).** The implementer produced none: every `pytest` invocation it tried was returned by the harness with `This command requires approval` and did not execute, so it could only disclose `Unrunnable here`. The orchestrator re-runs proofs itself at verification, so it ran each one: it applied the neutralization named below, captured the red run of the single detector node, restored by the inverse Edit, and ran the green. This record carries those receipts. Nothing in it is a claim by the implementer that a run happened.

- **Captures.** Red captures are `G1-red.txt` … `G8-red.txt`, `G19-red.txt`, `G20-red.txt` and `G21-red.txt`; the green capture is `L1-green.txt`. All are in `/private/tmp/claude-501/-Users-zwrose--superheroes-worktrees-superheroes-issue-1562-6d7c617f1b2d8fec/deb91a90-4d5c-42e8-8ce0-9d6443018573/scratchpad/bp/`, outside the repository.
- **Green.** `L1-green.txt` is `555 passed in 122.83s (0:02:02)`; it includes every node named here.
- **Restore, every element.** Restored by the inverse Edit; `git status --porcelain` empty after restore; green in `L1-green.txt`.
- **Reading a red.** Each red capture is one detector node run alone. For a parametrized node, the first failing assertion below is the first FAILED case in the capture, and the FAILED ids are listed in capture order. `T` in a node name is the test file above.

## Per-element receipts

Neutralized inside `core_md.py` / `configure_view.py` by a targeted Edit. Token literals are spelled out as strings in the tests (and `test_literal_pins` pins the constants), not reached through the module constants.

### G1 — not-an-object (refusal)

- **Neutralization applied.** The not-dict branch of `validate_sandbox_access` returns `[]`.
- **Node.** `T::test_validate_not_an_object`
- **First failing assertion** (`G1-red.txt`):

```
E       AssertionError: []
```

- **FAILED: 5.** `'pypi.org'`, `[]`, `None`, `5`, `['allowedDomains']`.

### G2 — unknown field (refusal)

- **Neutralization applied.** `if False and key not in SANDBOX_ACCESS_FIELDS:` on the `for key in value` unknown-key check (not the planned skip of the whole loop).
- **Node.** `T::test_validate_unknown_field`
- **First failing assertion** (`G2-red.txt`):

```
E       AssertionError: []
```

- **FAILED: 1.** `test_validate_unknown_field`.

### G3 — domains not a list (refusal)

- **Neutralization applied.** The `isinstance(domains, list)` check's condition replaced with `False` (`if False:`).
- **Node.** `T::test_validate_domains_not_a_list`
- **First failing assertion** (`G3-red.txt`):

```
E       AssertionError: assert 'sandbox-acce...omain-invalid' == 'sandbox-access-not-a-list'
```

- **FAILED: 4.** `'pypi.org'`, `None`, `{'a': 1}`, `5`. (`None` and `5` fail with `TypeError: ... is not iterable` out of the now-unguarded loop.)

### G4 — domain invalid (refusal)

- **Neutralization applied.** `_sandbox_domain_ok` returns `True`.
- **Node.** `T::test_validate_domain_invalid` (ids are the `repr` of each form, so the red names the forms that went through).
- **First failing assertion** (`G4-red.txt`):

```
E       AssertionError: []
```

- **FAILED: 22.** `'*'`, `'*.com'`, `'*.'`, `'a*.example.com'`, `'*.*.example.com'`, `'*.a*.com'`, `'https://pypi.org'`, `'ftp://x.org'`, `'pypi.org/simple'`, `'pypi.org:443'`, `' pypi.org'`, `'pypi.org '`, `'pypi org'`, `'pypi.org\\n'`, `''`, `'.pypi.org'`, `'pypi..org'`, `'pypi.org.'`, `5`, `None`, `True`, `['pypi.org']`.

### G5 — not a bool (refusal)

- **Neutralization applied.** `type(value[flag]) is not bool` → `not value[flag]`.
- **Node.** `T::test_validate_flag_not_a_bool`
- **First failing assertion** (`G5-red.txt`):

```
E       AssertionError: []
```

- **FAILED: 6** (8 passed: the falsy forms `0`, `None`, `[]`, `{}`, which `not value[flag]` still refuses). `1-localPorts`, `1-localSockets`, `'true'-localPorts`, `'true'-localSockets`, `'false'-localPorts`, `'false'-localSockets`.

### G6 — paths not a list (refusal)

- **Neutralization applied.** The `isinstance(paths, list)` check's condition replaced with `False` (`if False:`).
- **Node.** `T::test_validate_paths_not_a_list`
- **First failing assertion** (`G6-red.txt`; the capture's own `...` elision):

```
E       AssertionError: [{'field': 'extraWritePaths', 'index': 0, 'reason': 'sandbox-access-path-is-root', 'accepted': 'an absolute path below...n': 'sandbox-access-path-not-absolute', 'accepted': 'an absolute path such as /Users/me/Library/Caches/ms-playwright'}]
```

- **FAILED: 4.** `'/tmp/x'`, `None`, `{'a': 1}`, `5`.

### G7 — path not absolute (refusal)

- **Neutralization applied.** The `not os.path.isabs(entry)` leg dropped.
- **Node.** `T::test_validate_path_not_absolute`
- **First failing assertion** (`G7-red.txt`):

```
E       AssertionError: []
```

- **FAILED: 6** (3 passed: `5`, `None`, `['/a']`, which a separate non-string check still refuses). `'x/y'`, `'~/x'`, `'~'`, `''`, `'.'`, `'../x'`.

### G8 — path is root (refusal)

- **Neutralization applied.** The root check's condition (`not os.path.normpath(entry).strip("/")`) replaced with `False`.
- **Node.** `T::test_validate_path_is_root`
- **First failing assertion** (`G8-red.txt`):

```
E       AssertionError: []
```

- **FAILED: 6.** `'/'`, `'//'`, `'/.'`, `'///'`, `'/..'`, `'/a/..'`.

### G19 — configure view (display)

- **Neutralization applied.** `_sandbox_access_view_lines` returns only the heading.
- **Nodes.** `T::test_view_all_off_when_key_absent` and `T::test_view_configured_values_four_lines`, both in the one capture, each red on its own.
- **First failing assertion** (`G19-red.txt`, `test_view_all_off_when_key_absent`):

```
E       AssertionError: assert ['### Sandbox access'] == ['### Sandbox...ff (offline)']
```

- **First failing assertion** (`G19-red.txt`, `test_view_configured_values_four_lines`):

```
E       AssertionError: assert ['### Sandbox access'] == ['### Sandbox...ers/me/cache']
```

- **FAILED: 2.** `test_view_all_off_when_key_absent`, `test_view_configured_values_four_lines`.

### G20 — carry-forward (preservation)

- **Neutralization applied.** The `SANDBOX_ACCESS_KEY` carry in `confirm_all` removed.
- **Node.** `T::test_carry_forward_confirm_all_keeps_key_byte_equal`
- **First failing assertion** (`G20-red.txt`):

```
E       KeyError: 'sandboxAccess'
```

- **FAILED: 3.** `valid-unnormalized`, `malformed`, `not-a-dict`.

### G21 — `read_sandbox_access` repo-root-unavailable branch (WO-1b, #1564)

- **Guarded element and axis.** The `except RepoRootUnavailable:` branch of `read_sandbox_access` in `plugins/superheroes/lib/core_md.py` (refusal: an unresolvable repo root reads as `access` None, reason `repo-root-unavailable`, never as all-off).
- **Detector.** `T::test_read_repo_root_unavailable`, repaired in WO-1b so its fixture monkeypatches `CM.core_path` to raise `CM.RepoRootUnavailable("no root")` (the prior fixture, a path under `tmp_path`, never raised and read `core-md-absent`).
- **Neutralization applied.** The branch returns `dict(base, reason="repo-root-unavailable", access=sandbox_access_all_off())`.
- **First failing assertion** (`G21-red.txt`):

```
E       AssertionError: assert {'allowedDomains': [], 'localPorts': False, 'localSockets': False, 'extraWritePaths': []} is None
```

- **FAILED: 1.** `test_read_repo_root_unavailable`.

## Notes the reader of the proof needs

- **G8 and `//`.** The order says `//` normalizes to `/`. Measured on the pinned interpreter: `os.path.normpath("//")` is `"//"` (POSIX keeps exactly two leading slashes). The root check is therefore `not os.path.normpath(entry).strip("/")`, which refuses `/`, `//`, `/.`, `///`, `/..` and `/a/..`. Neutralizing G8 reddened every form in `test_validate_path_is_root`: all six.
- **G20 chokepoint.** The same carry-forward is also covered at `parse_core` / `render_core` (`test_carry_forward_parse_render_round_trip`) and `read` (`test_carry_forward_read_exposes_raw`). Those are extra detectors beyond the declared set and have no proof of their own.
