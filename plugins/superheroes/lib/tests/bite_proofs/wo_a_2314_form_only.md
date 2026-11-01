# WO-A2 (#2314) bite-proofs — form-only re-issue route, delete rule in the implementer template

Guarded-element set: the order named two elements, one per detector (a, b). The order declared no
wider set; each detector guards one element.

All runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest <node> -q`, from
the worktree root. No receipt below holds a secret, token, or private URL; nothing was redacted.
Each red run states which parametrized cases failed; the node ids below are the exact function ids
the order named (pytest runs every parameter of the function).

---

## (a) `test_a_route_is_valid_from_any_refuser`

**Guarded element:** `refusals_fault` in `plugins/superheroes/lib/command_refusals.py`, the
`if "route" in entry and entry["route"] is not None:` block (line 88). Axis: a non-blank `route`
is valid on an entry from any refuser (permission, hook, sandbox); only a blank route is refused.

**Neutralization:** with the Edit tool, inserted inside that block, directly after the blank-route
check and at the same indentation as that check's `if`:
```
                if by != "hook" and by != "sandbox":
                    return where + ".route needs refusedBy hook or sandbox"
```

**Command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_command_refusals.py::test_a_route_is_valid_from_any_refuser -q
```

**Raw red:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F..                                                                      [100%]
=================================== FAILURES ===================================
______________ test_a_route_is_valid_from_any_refuser[permission] ______________

refuser = 'permission'

    @pytest.mark.parametrize("refuser", ["permission", "hook", "sandbox"])
    def test_a_route_is_valid_from_any_refuser(refuser):
        # axis: a non-blank route is valid with any refuser (a form-only re-issue, whatever the refuser); a blank one is not
        assert not hasattr(CR, "ROUTE_REFUSED_BY")
>       assert CR.refusals_fault([_entry(refusedBy=refuser, hook=None, route="git status")]) is None
E       AssertionError: assert 'refusals[0].route needs refusedBy hook or sandbox' is None
E        +  where 'refusals[0].route needs refusedBy hook or sandbox' = <function refusals_fault at 0x7f38d657c220>([{'command': 'git push', 'refusedBy': 'permission', 'hook': None, 'next': 'stopped', ...}])
E        +    where <function refusals_fault at 0x7f38d657c220> = CR.refusals_fault

/home/user/wt-2314-a/plugins/superheroes/lib/tests/test_command_refusals.py:124: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_command_refusals.py::test_a_route_is_valid_from_any_refuser[permission]
1 failed, 2 passed in 1.91s
```
The red is on the claimed axis: the permission case fails with the re-inserted refusal token
`refusals[0].route needs refusedBy hook or sandbox`; the hook and sandbox cases, which the inserted
guard lets through, pass.

**Restore:** by the inverse Edit, removed exactly the two inserted lines.

**Restore receipt:** the block again ends
```
            if "route" in entry and entry["route"] is not None:
                if _blank(entry["route"]):
                    return where + ".route"
        return None
```
and `git diff --stat HEAD -- plugins/superheroes/lib/command_refusals.py plugins/superheroes/agents/implementer.md`
printed nothing (exit 0).

**Raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
...                                                                      [100%]
3 passed in 1.43s
```

---

## (b) `test_census_delete_rule_implementer_md`

**Guarded element:** the `**Deletes.**` paragraph in `plugins/superheroes/agents/implementer.md`
(line 57). Axis: the delete rule (`CR.DELETE_RULE`) reaches the implementer template.

**Neutralization:** with the Edit tool, removed the whole paragraph and the blank line after it:
```
**Deletes.** Never put `rm`, or any other delete, inside a compound command: not after `&&`, `||`
or `;`, not in a pipe, and not inside `bash -c` or a subshell. A delete is always its own plain
call, one path per call.

```

**Command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_command_refusals.py::test_census_delete_rule_implementer_md -q
```

**Raw red** (the `body = '--- name: implementer ...'` repr in the last assertion lines is cut by
pytest itself; nothing was edited out by hand):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
____________________ test_census_delete_rule_implementer_md ____________________

    def test_census_delete_rule_implementer_md():
        with open(_IMPLEMENTER_MD, encoding="utf-8") as fh:
            body = " ".join(fh.read().split())
        # axis: the delete rule reaches the implementer template — see bite-proof record wo_a_2314_form_only
>       assert " ".join(CR.DELETE_RULE.split()) in body
E       assert 'Never put `rm`, or any other delete, inside a compound command: not after `&&`, `||` or `;`, not in a pipe, and not inside `bash -c` or a subshell. A delete is always its own plain call, one path per call.' in '--- name: implementer description: Internal build subagent — implements one scoped work order dispatched by the Workh...d out of scope. - Return per the **Short structured return** rule above. Nothing beyond that — no verdict, no "ready."'
E        +  where 'Never put `rm`, or any other delete, inside a compound command: not after `&&`, `||` or `;`, not in a pipe, and not inside `bash -c` or a subshell. A delete is always its own plain call, one path per call.' = <built-in method join of str object at 0x155bfd8>(['Never', 'put', '`rm`,', 'or', 'any', 'other', ...])
E        +    where <built-in method join of str object at 0x155bfd8> = ' '.join
E        +    and   ['Never', 'put', '`rm`,', 'or', 'any', 'other', ...] = <built-in method split of str object at 0x7f67db56e930>()
E        +      where <built-in method split of str object at 0x7f67db56e930> = 'Never put `rm`, or any other delete, inside a compound command: not after `&&`, `||` or `;`, not in a pipe, and not inside `bash -c` or a subshell. A delete is always its own plain call, one path per call.'.split
E        +        where 'Never put `rm`, or any other delete, inside a compound command: not after `&&`, `||` or `;`, not in a pipe, and not inside `bash -c` or a subshell. A delete is always its own plain call, one path per call.' = CR.DELETE_RULE

/home/user/wt-2314-a/plugins/superheroes/lib/tests/test_command_refusals.py:301: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_command_refusals.py::test_census_delete_rule_implementer_md
1 failed in 6.88s
```
The red is on the claimed axis: the canonical delete-rule text is absent from the implementer
template body.

**Restore:** by the inverse Edit, reinserted the paragraph and its trailing blank line between the
paragraph ending `under rung 3 or rung 4 — you stop and report.` and `**Unscopable wide-gate order defect.**`.

**Restore receipt:** the restored text, quoted back:
```
**Deletes.** Never put `rm`, or any other delete, inside a compound command: not after `&&`, `||`
or `;`, not in a pipe, and not inside `bash -c` or a subshell. A delete is always its own plain
call, one path per call.
```
and `git diff --stat HEAD -- plugins/superheroes/lib/command_refusals.py plugins/superheroes/agents/implementer.md`
printed nothing (exit 0), so the file is byte-clean against HEAD.

**Raw green:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.41s
```
