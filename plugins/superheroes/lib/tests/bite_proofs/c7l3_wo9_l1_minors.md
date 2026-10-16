# Bite-proof record: the lowercase Nit-cap test reaches the cap

Detector: `plugins/superheroes/lib/tests/test_round_driver.py::test_mechanical_compile_nit_cap_lowercase_equivalent_to_exact_case`

Guarded element: the case-insensitive severity check in `_nit_cap` (`plugins/superheroes/lib/round_driver.py`,
`circuit_breaker.canonical_severity(f.get("severity")) == "Nit"`). Axis: a lowercase `nit` that reaches the cap counts
toward it like `Nit`.

## What the fixture now does

Each of the nine findings states a consequence and carries `consequenceKind: code-quality`, so it survives compile
(a finding with no stated consequence is refused there, before the cap runs). The test also asserts the exact-case run
really collapsed (`(5, 1, 6)` kept Nits, summary rows, rows), so a cap that never acted cannot pass.

## Entry point measured: `mechanical_compile` alone cannot reach the lowercase path

`mechanical_compile` sets `fc["severity"] = circuit_breaker.effective_severity(...)` on every kept finding before it
calls `_nit_cap`, so the cap only ever sees the canonical `Nit` through that entry point.

Neutralization applied (one line, `round_driver.py` ~885):
`circuit_breaker.canonical_severity(f.get("severity")) == "Nit"` -> `f.get("severity") == "Nit"`

With only the `mechanical_compile` comparison in the test, the neutralized run stayed green:

    .                                                                        [100%]
    1 passed in 1.64s

So the test also calls `RD._nit_cap` directly with the lowercase list; that is the only way to put `nit` in front of
the cap.

## Red (neutralization applied, test calls `_nit_cap` directly)

    F                                                                        [100%]
    =================================== FAILURES ===================================
    ...
            assert _post_cap_counts(capped_exact) == (RD._NIT_CAP, 1, RD._NIT_CAP + 1)
    >       assert _post_cap_counts(capped_lower) == _post_cap_counts(capped_exact)
    E       assert (9, 0, 9) == (5, 1, 6)
    E         At index 0 diff: 9 != 5
    E         Use -v to get more diff

    /home/user/wt-1869-wo3/plugins/superheroes/lib/tests/test_round_driver.py:3154: AssertionError
    =========================== short test summary info ============================
    FAILED plugins/superheroes/lib/tests/test_round_driver.py::test_mechanical_compile_nit_cap_lowercase_equivalent_to_exact_case
    1 failed in 1.61s

## Restore and green

Restored by the inverse edit: `f.get("severity") == "Nit"` -> `circuit_breaker.canonical_severity(f.get("severity")) == "Nit"`.
`git diff --quiet plugins/superheroes/lib/round_driver.py` exits 0 afterwards.

    .                                                                        [100%]
    1 passed in 1.51s
