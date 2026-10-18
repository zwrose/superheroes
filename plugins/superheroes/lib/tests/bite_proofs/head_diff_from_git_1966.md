# WO-2 bite-proof — post-fix diff from git (#1966)

Guarded-element set (declared by the order): G1 the mismatch comparison, G2 git as the source when
nothing is supplied, G3 the unverifiable park, G4 the session generation fence. Each entry below is
one targeted neutralization in `round_driver.py`, the detector run alone as one test node, the
restore by the inverse edit, and the restored lines quoted back. No capture is redacted or elided;
each is far under the 32 KiB bound. Runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/pyc -m pytest <node> -q`.

## G1 — the mismatch comparison

- **Guarded element:** `round_driver.py` `_fold_fixer`, the `elif _norm_newlines(supplied) == _norm_newlines(git_text):` row (line 5153).
- **Axis:** a readable supplied diff that differs from git's is refused (`head-diff-mismatch`), never accepted as the surface.
- **Neutralization:** `elif _norm_newlines(supplied) == _norm_newlines(git_text):` → `elif True:`.
- **Detector:** `plugins/superheroes/lib/tests/test_head_diff_from_git_1966.py::test_t2_mismatched_supplied_diff_refuses_on_the_cli_path[fix-only]`.
- **Raw red:** `1 failed in 1.94s`; failing assertion in `_assert_parked` (`test_head_diff_from_git_1966.py:226`):

```
>       assert state["terminal"] == "cannot-certify"
E       AssertionError: assert None == 'cannot-certify'
FAILED plugins/superheroes/lib/tests/test_head_diff_from_git_1966.py::test_t2_mismatched_supplied_diff_refuses_on_the_cli_path[fix-only]
```

- **Restore:** inverse edit `elif True:` → the original condition.
- **Restore receipt (quoted back, `grep -n`):** `5153:            elif _norm_newlines(supplied) == _norm_newlines(git_text):`
- **Raw green:** `. [100%]` / `1 passed in 2.03s`.

## G2 — git is the source when nothing is supplied

- **Guarded element:** `round_driver.py` `_fold_fixer`, the `head_check = "none-supplied"` row (line 5150).
- **Axis:** with a repository and nothing supplied, the head diff and its source come from git, so the round audits the fixes.
- **Neutralization:** added `head, head_source = None, "unknown"` after `head_check = "none-supplied"`.
- **Detector:** `plugins/superheroes/lib/tests/test_head_diff_from_git_1966.py::test_t4_no_supplied_diff_derives_git_and_schedules_the_fix_audit`.
- **Raw red:** `1 failed in 2.21s`:

```
>       assert rec["headDiffSource"] == "git"
E       AssertionError: assert 'unknown' == 'git'
E         - git
E         + unknown
FAILED plugins/superheroes/lib/tests/test_head_diff_from_git_1966.py::test_t4_no_supplied_diff_derives_git_and_schedules_the_fix_audit
```

- **Restore:** inverse edit removed the added line.
- **Restore receipt (quoted back, `sed -n 5147,5158p`):**

```
        if refuse is None:
            head, head_source = git_text, "git"
            if not present:
                head_check = "none-supplied"
            elif not readable:
                head_check = "supplied-unreadable"
```

- **Raw green:** `. [100%]` / `1 passed in 1.96s`.

## G3 — the unverifiable park

- **Guarded element:** `round_driver.py` `_fold_fixer`, the `if present:` branch that sets `park_detail` to `head-diff-unverifiable` (line 5160).
- **Axis:** a derivation git cannot make beside a supplied diff parks; it never falls through to the unknown (full-panel) path.
- **Neutralization:** `if present:` → `if False:` (the park branch dropped, so the failed derivation takes the unknown path).
- **Detector:** `plugins/superheroes/lib/tests/test_head_diff_from_git_1966.py::test_e5_git_refusal_beside_a_supplied_diff_parks_unverifiable`.
- **Raw red:** `1 failed in 2.04s`:

```
>       assert state["certification"]["reason"].startswith(token)
E       AssertionError: assert False
E        +  where False = <built-in method startswith of str object at 0x7f48ae3f97d0>('head-diff-unverifiable')
E        +    where <built-in method startswith of str object at 0x7f48ae3f97d0> = 'panel-diff-underivable: baseRef not a commit'.startswith
FAILED plugins/superheroes/lib/tests/test_head_diff_from_git_1966.py::test_e5_git_refusal_beside_a_supplied_diff_parks_unverifiable
```

- **Restore:** inverse edit `if False:` → `if present:`.
- **Restore receipt (quoted back, `sed -n 5158,5163p`):**

```
        else:
            head, head_source, head_check = None, "unknown", "unverifiable"
            if present:
                park_detail = "%s: git cannot verify the supplied %s head diff: %s" % (
                    HEAD_DIFF_UNVERIFIABLE_CAUSE, supplied_source, refuse)
```

- **Raw green:** `. [100%]` / `1 passed in 2.00s`.

## G4 — the generation fence

- **Guarded element:** `round_driver.py:271` `SESSION_GENERATION = 6`, read by the upgrade gate that refuses any session whose `sessionGeneration` is not the current integer.
- **Axis:** the previous generation (5) is refused with `session-from-earlier-version`, not resumed.
- **Authorized detector edit:** the value `5` with id `five-previous` was added to the parametrize list of `test_session_pickup_and_upgrade_1721.py::test_e4_a_generation_that_is_not_the_current_integer_is_refused` (no case pinned the previous generation before). The detector is unedited during the proof.
- **Neutralization:** `SESSION_GENERATION = 6` → `SESSION_GENERATION = 5`.
- **Detector:** `plugins/superheroes/lib/tests/test_session_pickup_and_upgrade_1721.py::test_e4_a_generation_that_is_not_the_current_integer_is_refused[five-previous]`.
- **Raw red:** `1 failed in 1.42s`; generation 5 passed the gate (it reached the meta read instead of the refusal):

```
>       assert out["reason"] == TOKEN, out
E       AssertionError: {'ok': False, 'reason': 'base-meta-unreadable', 'detail': "meta.json not readable: [Errno 2] No such file or directory: '/tmp/claude-0/pytest-of-root/pytest-17/test_e4_a_generation_that_is_n0/light/meta.json'"}
E       assert 'base-meta-unreadable' == 'session-from-earlier-version'
FAILED plugins/superheroes/lib/tests/test_session_pickup_and_upgrade_1721.py::test_e4_a_generation_that_is_not_the_current_integer_is_refused[five-previous]
```

- **Restore:** inverse edit `SESSION_GENERATION = 5` → `SESSION_GENERATION = 6`.
- **Restore receipt (quoted back, `grep -n`):** `271:SESSION_GENERATION = 6`; `git diff --stat -- plugins/superheroes/lib/round_driver.py` printed nothing after the four restores, so `round_driver.py` is byte-clean against the build's head.
- **Raw green:** `. [100%]` / `1 passed in 1.35s`.
