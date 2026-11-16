# #2504 bite-proof — WO-C: the append-before-propose negative test selects its clause by text, not line number

Detector changed: `test_negative_discuss_open_inverted_append_before_propose_one_clause` in `plugins/superheroes/lib/tests/test_disposition_flow.py`. It used to select the clause it inverts with `if i == 47:`; it now selects the one line that starts with `For each owner call that will be delivered in batch 1 or batch 2`, after asserting that exactly one line of the file starts with that text (the message names the clause as missing or duplicated).

Declared guarded-element set: one element, **S1**. Redaction: none needed. Each capture omits only the first line the runner prints (`warning: The UV_NATIVE_TLS environment variable is deprecated ...`); everything else is verbatim.

## Earlier red (orchestrator, before this change)

The unedited test, run against the moved clause (line 49 in `skills/discuss-open-decisions/SKILL.md`, was line 47) on head `583363bf`, failed with `AssertionError: detector did not bite: no exception raised`. This record did not re-run that; it is the orchestrator's receipt.

## S1 — the test's selection of the clause it inverts

Guarded element: `test_disposition_flow.py:466-470` (the `for line in lines: if line.startswith(clause_start):` selection inside the changed test). Axis: the test inverts the append-before-propose clause wherever it sits in the file.

Neutralization (inside the changed test, line 468): `inverted.append(line.replace("**before**", "**after**"))` → `inverted.append(line.replace("**before**", "**before**"))`, so the selected line's replacement is a no-op.

Command (from the worktree root):

```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2504c -m pytest plugins/superheroes/lib/tests/test_disposition_flow.py -q -p no:cacheprovider -k test_negative_discuss_open_inverted_append_before_propose_one_clause
```

Raw red (neutralized):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_negative_discuss_open_inverted_append_before_propose_one_clause _____

    def test_negative_discuss_open_inverted_append_before_propose_one_clause():
        base = _read_plugin(_DISCUSS_OPEN)
        lines = base.splitlines()
        clause_start = "For each owner call that will be delivered in batch 1 or batch 2"
        matching = [line for line in lines if line.startswith(clause_start)]
        assert len(matching) == 1, (
            "expected exactly one line of %s to start with the append-before-propose "
            "clause %r, found %d (clause missing or duplicated)"
            % (_DISCUSS_OPEN, clause_start, len(matching))
        )
        inverted = []
        for line in lines:
            if line.startswith(clause_start):
                inverted.append(line.replace("**before**", "**before**"))
            else:
                inverted.append(line)
        texts = {
            _DISCUSS_OPEN: "\n".join(inverted),
            _OWNER_DECISIONS: "\n".join(_PINNED_OWNER_DECISIONS_HEADINGS),
        }
>       _expect_assertion_error(
            lambda: _assert_discuss_open_holder_pins(texts),
            match="append-after-propose in pinned ordering clause",
        )

/home/user/superheroes-wt-2504/plugins/superheroes/lib/tests/test_disposition_flow.py:475: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/superheroes-wt-2504/plugins/superheroes/lib/tests/test_disposition_flow.py:204: in _expect_assertion_error
    return _expect_error(fn, AssertionError, match=match)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

fn = <function test_negative_discuss_open_inverted_append_before_propose_one_clause.<locals>.<lambda> at 0x7fe06848eac0>
exc_type = <class 'AssertionError'>
match = 'append-after-propose in pinned ordering clause'

    def _expect_error(fn, exc_type, *, match):
        exc_name = exc_type.__name__
        try:
            fn()
        except exc_type as exc:
            if not re.search(match, str(exc)):
                raise AssertionError(
                    "detector raised %s but message %r does not match %r"
                    % (exc_name, str(exc), match)
                ) from None
            return exc
        except BaseException as exc:  # noqa: BLE001
            raise AssertionError(
                "detector did not bite: expected %s, got %s: %s"
                % (exc_name, type(exc).__name__, exc)
            ) from None
>       raise AssertionError("detector did not bite: no exception raised")
E       AssertionError: detector did not bite: no exception raised

/home/user/superheroes-wt-2504/plugins/superheroes/lib/tests/test_disposition_flow.py:200: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_disposition_flow.py::test_negative_discuss_open_inverted_append_before_propose_one_clause
1 failed, 19 deselected in 0.25s
```

Restore: inverse edit, `"**before**", "**before**"` → `"**before**", "**after**"`.

Restore receipt (restored line quoted back, `test_disposition_flow.py:468`): `            inverted.append(line.replace("**before**", "**after**"))`. A search of the file for `**before**` and `**after**` finds only that line.

Raw green (restored):

```
.                                                                        [100%]
1 passed, 19 deselected in 4.62s
```

Full-file run after the change, before the neutralization (not part of the proof; the one full-file run in the budget):

```
....................                                                     [100%]
20 passed in 0.46s
```
