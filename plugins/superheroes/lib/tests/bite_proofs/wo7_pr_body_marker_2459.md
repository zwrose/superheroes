# Bite-proof record: WO-7 (issue 2459) `prove` never reads a failed body save as a body

Detector: `test_cli_prove_pr_body_that_is_not_a_vetted_body_refuses_before_any_git` (six cases:
empty, blank, github-404-json, no-marker, marker-inside-text, marker-twice) in
`plugins/superheroes/lib/tests/test_stack_linear.py`, guarding the `--pr-body` marker check in
`_prove_cli_inputs` (`plugins/superheroes/lib/stack_linear.py`). Each case runs `main([...])` with a
recording `_GitRun` and asserts exit 1, reason `pr-body-not-vetted`, the PR named in the detail, and
`run.calls == []`.

Guarded-element set (declared by the order): C1, C2, C3. Receipts below are redacted of nothing
(no secrets in them); the red captures are the pytest summaries as printed, with the long
`-q` header line `warning: The UV_NATIVE_TLS ...` omitted (a tool deprecation notice, not test output).

## C1 - the exactly-one-marker decision (axis: marker count other than one is refused)

- Neutralization: in `_prove_cli_inputs`, `if marker_lines != 1:` replaced by `if False:`.
- Command: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo7 -m pytest plugins/superheroes/lib/tests/test_stack_linear.py -q -p no:cacheprovider --tb=short -k not_a_vetted_body`
- Raw red (all six cases red on `assert code == 1 and ...`, the mutant exits 0 and proves):

```
FFFFFF                                                                   [100%]
E   assert (0 == 1)     (each of the six cases, test_stack_linear.py:1477)
FAILED ...::test_cli_prove_pr_body_that_is_not_a_vetted_body_refuses_before_any_git[empty]
FAILED ...[blank]
FAILED ...[github-404-json]
FAILED ...[no-marker]
FAILED ...[marker-inside-text]
FAILED ...[marker-twice]
6 failed, 220 deselected in 1.01s
```

- Restore: inverse edit, `if False:` back to `if marker_lines != 1:`.
- Restore receipt: `Grep marker_lines` after the restore showed `stack_linear.py:797:        if marker_lines != 1:`.
- Raw green (same command): `6 passed, 220 deselected in 0.75s`.

## C2 - the check's placement before any git command (axis: no git command runs for a non-vetted body)

- Neutralization (two targeted edits): the in-loop check made inert, `if marker_lines != 1:` to
  `if False:`; and the same count re-applied after the `prove(...)` call in `main`, inserted after
  `remote=args.remote, today=today, run=run, bodies=bodies)`:
  `for pr_n, body_n in bodies.items(): if sum(1 for ln in body_n.splitlines() if ln.strip() == ADVISOR_VET_MARKER) != 1: result = _prove_refused(REASON_PR_BODY_NOT_VETTED, "--pr-body %d file: no advisor-vet marker line" % pr_n); break`
  so the refusal still comes out, with the right reason and PR, but only after git ran.
- Command: same `-k not_a_vetted_body`.
- Raw red: five cases red on the no-git assertion:

```
E   AssertionError: assert [['git', 'rev...ommit}'], ...] == []
E     Left contains 21 more items, first extra item: ['git', 'rev-parse', '--is-shallow-repository']
(test_stack_linear.py:1480 `assert run.calls == []`, cases empty, blank, github-404-json, no-marker, marker-inside-text)
```

  The sixth case, marker-twice, went red one assertion earlier, at the detail assertion
  (`test_stack_linear.py:1479`), because the mutant's fixed detail text says "no advisor-vet marker
  line" rather than "2 advisor-vet marker lines"; that case is red on the detail axis, not the
  no-git axis, in this mutant. Summary: `6 failed, 220 deselected in 0.97s`.
- Restore: both inverse edits (the inserted `for` block removed; `if False:` back to
  `if marker_lines != 1:`).
- Restore receipt: `git diff -U0 -- plugins/superheroes/lib/stack_linear.py` after the restore shows
  only the two intended additions (the constants at line 61 and the check at lines 792-803); no
  `if False:` and no `pr_n` remain.
- Raw green: whole file after restore, `226 passed in 3.37s`.

## C3 - the recipe's checked-read sentence in `merge-train.md` item 4 (e)

Prose with no detector: it is an instruction to the advisor, and nothing in this change fails when
it is wrong. No proof is owed. The detector for the failure it guards is C1 (a failed or empty save
is refused by `prove` whatever the recipe says).
