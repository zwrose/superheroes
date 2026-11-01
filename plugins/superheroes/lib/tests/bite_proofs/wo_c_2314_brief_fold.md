# WO-C (#2314) bite-proofs — delete rule cited by the in-session fix step; permission-route test correction

Guarded-element set: the order declared one detector element, (a) item 8's citation in
`auto-fix-loop.md`. The B1 test change (b) is a correction of an existing assertion, not a new
detector; its record is the red→green of the existing node.

All runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest <node> -q -p no:cacheprovider`,
from the worktree root. No receipt below holds a secret, token, or private URL; nothing was redacted.

---

## (a) `test_census_delete_rule_apply_fixes_step`

**Guarded element:** item 8 of the numbered list under "**What the session does.**" in
`plugins/superheroes/skills/review-code/reference/auto-fix-loop.md` § Applying the fixes (line 596),
specifically its citation of `DELETE_RULE` beside `lib/command_refusals.py`. Axis: the in-session fix
step is bound to the delete rule by citation, not by copy.

**Neutralization:** with the Edit tool, in item 8, replaced `DELETE_RULE` with `the rule`, so the text
read ``the delete rule (`the rule` in `lib/command_refusals.py`) binds``.

**Command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_command_refusals.py::test_census_delete_rule_apply_fixes_step -q -p no:cacheprovider
```

**Raw red** (the `section` repr in the last assertion line is cut by pytest itself; nothing was
edited out by hand):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
___________________ test_census_delete_rule_apply_fixes_step ___________________

    def test_census_delete_rule_apply_fixes_step():
        path = os.path.join(_PLUGIN_ROOT, "skills", "review-code", "reference", "auto-fix-loop.md")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        start = text.index("## Applying the fixes")
        end = text.find("\n## ", start + 1)
        section = text[start:] if end == -1 else text[start:end]
        # axis: the in-session fix step cites the delete rule by name and home — see bite-proof record wo_c_2314_brief_fold
>       assert "DELETE_RULE" in section
E       AssertionError: assert 'DELETE_RULE' in '## Applying the fixes\n\nWhen `next` returns `apply-fixes`, the build session fixes the batch itself, in its own work... No finding below blocking joins a fix batch unless a ruling names it; those\nsettle when the loop converges.\n\n---\n'

/home/user/wt-2314/plugins/superheroes/lib/tests/test_command_refusals.py:315: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_command_refusals.py::test_census_delete_rule_apply_fixes_step
1 failed in 1.39s
```
The red is on the claimed axis: with the citation replaced, the section no longer contains `DELETE_RULE`.

**Restore:** by the inverse Edit, replaced `the rule` with `DELETE_RULE` in item 8.

**Restore receipt:** the restored line, quoted back (line 596):
```
8. Never put a delete inside a compound command: the delete rule (`DELETE_RULE` in `lib/command_refusals.py`) binds this step as it binds every implementer order.
```

**Raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.27s
```

---

## (b) `test_validate_accepts_a_taken_route_from_any_refuser_and_refuses_a_blank_one` (correction, not a new detector)

**Element:** the existing node `test_validate_accepts_a_taken_route_and_refuses_one_on_a_permission_refusal`
in `plugins/superheroes/lib/tests/test_review_record_refusals.py`, which asserted the old rule (a
permission entry with a route is refused). `refusals_fault` now accepts a non-blank route from any
refuser, so the old assertion was wrong.

**Red (on the current head, before the change):** observed by the orchestrator, not by me:
`DID NOT RAISE Refusal`. I did not re-run it; no raw output of mine exists for this half.

**Change:** renamed to `test_validate_accepts_a_taken_route_from_any_refuser_and_refuses_a_blank_one`;
keeps the `ROUTED` accept; asserts a `permission` entry (`OTHER`) with `route="git status"` validates
and keeps its route; asserts a blank route (`"  "`) on a permission entry still raises `rr.Refusal`
(`review-account-invalid`, detail starting `commandRefusals[0]`).

**Raw green** (the whole file, command 1 of the budget):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.............................                                            [100%]
29 passed in 2.93s
```
