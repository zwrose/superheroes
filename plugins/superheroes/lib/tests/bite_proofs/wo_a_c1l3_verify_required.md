# C1-L3 WO-A (#2207) bite-proof — code review needs a verify command

**Provenance:** produced by WO-A, claude / the implementer cell the dispatcher resolved, on base
`5671c95e` plus uncommitted edits. **Method.** Each guarded element is neutralized on its own by one
targeted edit to production code (never the detector), the detector run unedited, the edit undone by
the exact inverse edit, the detector re-run. One neutralization live at a time. Tests selected with a
single `-k`.

Common command (run from the worktree root; `<file>` and `<name>` per row):

```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-a -m pytest plugins/superheroes/lib/tests/<file> -k <name> -q
```

The red captures below quote the decisive lines of each run (the failing assertion, its source line,
the FAILED line and the summary line); the `UV_NATIVE_TLS` warning line, the test-body echo and the
temp `tmp_path` lines are left out. Nothing in them is a secret; no redaction was needed.

## Guarded elements

| ID | Guarded element | Axis | Neutralized thing | Detector |
|---|---|---|---|---|
| E1 | `review_code_config.py` `resolve()` `verifyRefusal` for no command (core null/absent) | refusal is set when no command resolves | `None if configured else {…}` → `None if True else {…}` | `test_verify_required_c1l3.py::test_no_command_in_core_is_refused` |
| E2 | `resolve_verify_from_profile` reads a legacy `mode: review-only` line as no command | legacy review-only profile is refused | accept `mode: review-only` as a `command:` line | `test_legacy_profile_review_only_is_refused` |
| E3 | same, for `mode: unverified` | legacy unverified profile is refused | accept `mode: unverified` as a `command:` line | `test_legacy_profile_unverified_is_refused` |
| E4 | `verify_command_configured` normalises case and whitespace | `NONE` / `  none  ` / `None` are no command | drop `.strip().lower()` | `test_core_none_in_any_case_is_refused` |
| E5 | a configured command yields no refusal | refusal not set for a real command | `None if configured else {…}` → `None if False else {…}` | `test_configured_command_is_not_refused` |
| E6 | `review_base_guard.py` mismatch detail says "not supported" | plain refusal, names no read-only mode | restore the base detail `"PR base repo %r does not match origin %r"` | `test_review_base_guard.py::test_pr_mode_repo_mismatch_detail_is_the_plain_refusal` |

## E1 — resolve() sets verifyRefusal when no command resolves

- **neutralization:** `"verifyRefusal": None if configured else {` → `"verifyRefusal": None if True else {`
- **raw red** (exit 1):
```
F                                                                        [100%]
______________________ test_no_command_in_core_is_refused ______________________
>       assert out["verifyRefusal"] == _REFUSAL
E       assert None == {'reason': 'verify-command-required', 'message': "Code review is not available until a verify command is set. Code review needs a command that verifies this project's code; set one with /superheroes:configure."}
/home/user/wt-2207-a/plugins/superheroes/lib/tests/test_verify_required_c1l3.py:80: AssertionError
FAILED plugins/superheroes/lib/tests/test_verify_required_c1l3.py::test_no_command_in_core_is_refused
1 failed, 21 deselected in 0.30s
```
- **restore:** inverse edit.
- **restore receipt:** `review_code_config.py:149:        "verifyRefusal": None if configured else {`
- **raw green:** `1 passed, 21 deselected in 3.09s`

## E2 — legacy `mode: review-only` reads as no command

- **neutralization:** `if line.startswith("command:"):` → `if line.startswith(("command:", "mode: review-only")):`
- **raw red** (exit 1):
```
>       assert out["verifyRefusal"] == _REFUSAL
E       assert None == {'reason': 'verify-command-required', 'message': "Code review is not available until a verify command is set. …"}
/home/user/wt-2207-a/plugins/superheroes/lib/tests/test_verify_required_c1l3.py:97: AssertionError
FAILED plugins/superheroes/lib/tests/test_verify_required_c1l3.py::test_legacy_profile_review_only_is_refused
1 failed, 21 deselected in 0.36s
```
(the message text is elided in this quote with `…`; the run printed it whole, identical to E1's.)
- **restore:** inverse edit.
- **restore receipt:** `review_code_config.py:55:                if line.startswith("command:"):`
- **raw green:** `1 passed, 21 deselected in 0.36s`

## E3 — legacy `mode: unverified` reads as no command

- **neutralization:** `if line.startswith("command:"):` → `if line.startswith(("command:", "mode: unverified")):`
- **raw red** (exit 1):
```
>       assert out["verifyRefusal"] == _REFUSAL
E       assert None == {'reason': 'verify-command-required', 'message': "Code review is not available until a verify command is set. …"}
/home/user/wt-2207-a/plugins/superheroes/lib/tests/test_verify_required_c1l3.py:106: AssertionError
FAILED plugins/superheroes/lib/tests/test_verify_required_c1l3.py::test_legacy_profile_unverified_is_refused
1 failed, 21 deselected in 0.41s
```
(message text elided with `…` in this quote only.)
- **restore:** inverse edit.
- **restore receipt:** `review_code_config.py:55:                if line.startswith("command:"):`
- **raw green:** `1 passed, 21 deselected in 0.37s`

## E4 — case and whitespace `none` reads as no command

- **neutralization:** `return cmd.strip().lower() not in ("", "none")` → `return cmd not in ("", "none")`
- **raw red** (exit 1; all three parameters red):
```
FFF                                                                      [100%]
>       assert out["verifyRefusal"] == _REFUSAL
E       assert None == {'reason': 'verify-command-required', 'message': "Code review is not available until a verify command is set. …"}
FAILED …/test_verify_required_c1l3.py::test_core_none_in_any_case_is_refused[NONE]
FAILED …/test_verify_required_c1l3.py::test_core_none_in_any_case_is_refused[  none  ]
FAILED …/test_verify_required_c1l3.py::test_core_none_in_any_case_is_refused[None]
3 failed, 19 deselected in 0.48s
```
(message text elided with `…` in this quote only; the three tracebacks are identical, one shown.)
- **restore:** inverse edit.
- **restore receipt:** `review_code_config.py:30:    return cmd.strip().lower() not in ("", "none")`
- **raw green:** `3 passed, 19 deselected in 0.52s`

## E5 — a configured command yields no refusal

- **neutralization:** `"verifyRefusal": None if configured else {` → `"verifyRefusal": None if False else {`
- **raw red** (exit 1):
```
>       assert out["verifyRefusal"] is None
E       assert {'reason': 'verify-command-required', 'message': "Code review is not available until a verify command is set. …"} is None
/home/user/wt-2207-a/plugins/superheroes/lib/tests/test_verify_required_c1l3.py:124: AssertionError
FAILED plugins/superheroes/lib/tests/test_verify_required_c1l3.py::test_configured_command_is_not_refused
1 failed, 21 deselected in 0.34s
```
(message text elided with `…` in this quote only.)
- **restore:** inverse edit.
- **restore receipt:** `review_code_config.py:149:        "verifyRefusal": None if configured else {`
- **raw green:** `1 passed, 21 deselected in 3.10s`

## E6 — base-repo mismatch detail says not supported

- **neutralization:** the `detail` expression in the `REASON_REPO_MISMATCH` return replaced by the base text `"PR base repo %r does not match origin %r" % (pr_repo, base_repo)`.
- **raw red** (exit 1):
```
>       assert "reviewing this PR is not supported" in r["detail"]
E       assert 'reviewing this PR is not supported' in "PR base repo 'github.com/otherorg/widget' does not match origin 'github.com/acme/widget'"
/home/user/wt-2207-a/plugins/superheroes/lib/tests/test_review_base_guard.py:370: AssertionError
FAILED plugins/superheroes/lib/tests/test_review_base_guard.py::test_pr_mode_repo_mismatch_detail_is_the_plain_refusal
1 failed, 95 deselected in 0.74s
```
- **restore:** inverse edit.
- **restore receipt:** `review_base_guard.py:562:                "detail": ("reviewing this PR is not supported: code review reviews only PRs "`
- **raw green:** `1 passed, 95 deselected in 0.55s`

## Unproven part of E6

The two negative assertions in that test (`"read-only"` / `"review-only"` absent from the detail) are
**not discriminated** by the neutralization above: the base detail names neither word, so those two
assertions pass against it. Only the positive half ("reviewing this PR is not supported") is proven
to bite. Proving the negative half needs a second neutralization (append a read-only pointer to the
detail), which was not run: the order's 12-run bite-proof budget is one red and one green per element.
Its protection is unverified until that run is made.

## E6 negative legs — WO-D (#2207), run after the section above

**Provenance:** produced by WO-D, claude / the implementer cell the dispatcher resolved, on the
worktree with WO-A/B/C merged. These two entries close the "Unproven part of E6" section above. Same
method: one targeted edit to the production string in `review_base_guard.py` (never the detector), the
detector run unedited, the edit undone by the exact inverse edit, the detector re-run. The detector
was selected with `-k test_pr_mode_repo_mismatch_detail_is_the_plain_refusal` (the single guarding
node, narrower than the order's `-k mismatch`). Command, with `UV_NATIVE_TLS` warning line left out of
the quotes below:

```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-d -m pytest plugins/superheroes/lib/tests/test_review_base_guard.py -k test_pr_mode_repo_mismatch_detail_is_the_plain_refusal -q
```

The red captures quote the failing assertion, its source line, the FAILED line and the summary line;
the test-body echo and the temp `tmp_path` lines are left out. Nothing in them is a secret; no
redaction was needed.

### E6 leg 1 — detail names `read-only`

- **neutralization:** `review_base_guard.py:564` `"not this project's (%r)" % (pr_repo, base_repo)),` →
  `"not this project's (%r) (or use the read-only review)" % (pr_repo, base_repo)),`
- **raw red** (exit 1):
```
>       assert "read-only" not in r["detail"]
E       AssertionError: assert 'read-only' not in 'reviewing t...only review)'
E         
E         'read-only' is contained here:
E           r use the read-only review)
E         ?           +++++++++

plugins/superheroes/lib/tests/test_review_base_guard.py:371: AssertionError
FAILED plugins/superheroes/lib/tests/test_review_base_guard.py::test_pr_mode_repo_mismatch_detail_is_the_plain_refusal
1 failed, 95 deselected in 1.04s
```
- **restore:** inverse edit (the appended ` (or use the read-only review)` removed).
- **restore receipt:** `review_base_guard.py:564:                           "not this project's (%r)" % (pr_repo, base_repo)),`
- **raw green:** `1 passed, 95 deselected in 0.62s`

### E6 leg 2 — detail names `review-only`

- **neutralization:** `review_base_guard.py:564` `"not this project's (%r)" % (pr_repo, base_repo)),` →
  `"not this project's (%r) (or use review-only)" % (pr_repo, base_repo)),`
- **raw red** (exit 1):
```
>       assert "review-only" not in r["detail"]
E       AssertionError: assert 'review-only' not in 'reviewing t...review-only)'
E         
E         'review-only' is contained here:
E           ) (or use review-only)

plugins/superheroes/lib/tests/test_review_base_guard.py:372: AssertionError
FAILED plugins/superheroes/lib/tests/test_review_base_guard.py::test_pr_mode_repo_mismatch_detail_is_the_plain_refusal
1 failed, 95 deselected in 2.58s
```
- **restore:** inverse edit (the appended ` (or use review-only)` removed).
- **restore receipt:** `review_base_guard.py:564:                           "not this project's (%r)" % (pr_repo, base_repo)),`; `git diff plugins/superheroes/lib/review_base_guard.py` is empty after the restore.
- **raw green:** `1 passed, 95 deselected in 0.47s`
