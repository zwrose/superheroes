# WO-D1 (#1272, layer 2d) bite-proof — CR/CRLF fold in `_order_lint_text`

Declared guarded-element set: the two independently removable folds in
`round_driver._order_lint_text` — BP1, the budget/verify fold (proven by the implementer, re-run
by the orchestrator); BP2, the quoted-string loop fold for `GATE_GUIDANCE` /
`ratified_residuals` (proven by the orchestrator in a detached probe tree at the committed
state).

## BP1 — budget/verify fold (`test_verify_command_elision_survives_carriage_returns`)

**Guarded element:** `plugins/superheroes/lib/round_driver.py` `_order_lint_text`, the lines
`budget = order_lint.normalize_newlines(budget)` / `verify = order_lint.normalize_newlines(verify)`.
Axis: a CR/CRLF inside the owner's verify command must not defeat the budget-tail elision
against the already-folded order text. If it did, the owner's `{item}` token would reach the
lint and the emission would be refused with `order-placeholder-unfilled`.

**Neutralization** (targeted Edit, both call sites bound to their raw values):

```
-        budget = order_lint.normalize_newlines(budget)
+        budget = budget  # BITE-PROOF NEUTRALIZED
-        verify = order_lint.normalize_newlines(verify)
+        verify = verify  # BITE-PROOF NEUTRALIZED
```

**Command (red and green):**

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-d1 -m pytest "plugins/superheroes/lib/tests/test_round_driver_order_lint.py::test_verify_command_elision_survives_carriage_returns" -q -p no:cacheprovider
```

**Red run** (exit 1). This is an excerpt: the full capture is 16530 bytes and the elided middle
is the pytest traceback source listing. Redacted: pytest `tmp_path` values under the macOS
per-user temp directory.

```
FF                                                                       [100%]
=================================== FAILURES ===================================
_________ test_verify_command_elision_survives_carriage_returns[crlf] __________
...
E                   ValueError: order-render-refused:fixer-508e7896192355de:order-lint:order-placeholder-unfilled:item
...
__________ test_verify_command_elision_survives_carriage_returns[cr] ___________
...
E                   ValueError: order-render-refused:fixer-508e7896192355de:order-lint:order-placeholder-unfilled:item

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1272-7bfe57f757a3cc6a/plugins/superheroes/lib/round_driver.py:7456: ValueError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_driver_order_lint.py::test_verify_command_elision_survives_carriage_returns[crlf]
FAILED plugins/superheroes/lib/tests/test_round_driver_order_lint.py::test_verify_command_elision_survives_carriage_returns[cr]
2 failed in 6.64s
```

Both parametrizations went red with the exact token `order-placeholder-unfilled` (detail `item`).

**Restore:** the inverse Edit (no git discard).

**Restore receipt:** the restored lines as they read after the inverse Edit:

```
    if isinstance(budget, str):
        budget = order_lint.normalize_newlines(budget)
    if isinstance(verify, str):
        verify = order_lint.normalize_newlines(verify)
```

A search for `BITE-PROOF NEUTRALIZED` in `round_driver.py` finds nothing (grep exit 1).

**Green run** (exit 0):

```
..                                                                       [100%]
2 passed in 7.14s
```

Orchestrator re-run of BP1 in a detached probe tree at the committed state: red, exit 1, `2 failed`,
both `ValueError: order-render-refused:fixer-508e7896192355de:order-lint:order-placeholder-unfilled:item`;
green after the inverse Edit.

## BP2 — quoted-string loop fold (`GATE_GUIDANCE` / `ratified_residuals`)

**Guarded element:** `_order_lint_text`, the line `quoted = order_lint.normalize_newlines(quoted)`
inside the `for quoted in (ph.get("GATE_GUIDANCE"), context.get("ratified_residuals"))` loop.

**Neutralization** (targeted Edit in the probe tree):

```
-            quoted = order_lint.normalize_newlines(quoted)
+            quoted = quoted  # BITE2
```

**Red, test channel** (exit 1): `test_gate_guidance_elision_survives_crlf` fails on
`assert '{name}' not in 'PROLOGUE\nK...\nEPILOGUE\n'` — the guidance was not elided.
The test's production emission step (`_emit_fixer` with the seeded CRLF guidance) did NOT refuse under
this neutralization: the seeded guidance does not reach the order text with its CR intact on that
path, so the production-path red for this element is carried by the lint call below, not by emission.

**Red, exact token** (the same neutralized `_order_lint_text` output, graded by the lint):
`order_lint.check_text(lint_text, <empty repo>, kind="fixer")` →
`{"ok": false, "findings": [{"token": "order-placeholder-unfilled", "detail": "name"}]}`.

**Restore:** the inverse Edit; the probe tree then showed 0 dirty paths.

**Green** (exit 0): `3 passed` (T1 both parametrizations + T2); the lint call on the restored text
returns `{"ok": true}`.
