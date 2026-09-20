# Bite-proof — the order lint's narrow verify-command elision (C13 bring-current, #1272)

**Change under proof:** `round_driver._order_lint_text` sources the owner's verify command from
the session config (`verify_command`, carried on the order render context) and elides it **only
where it rides inside the `VERIFY_BUDGET` block**, replacing the retired `VERIFY_COMMAND`
placeholder read that C13 layer 2d left dead.

**Guarded element (one):** the narrow elision itself — the owner's command leaves the fixer
order's lint text while the driver's own scoped-budget prose (its target-file list and the paths
in it) stays graded.

**Probe mechanics:** targeted revertible edit through the host's edit action on the committed
head `928ef52f`; reverted by the inverse edit; the restore receipt below is `git status
--porcelain` on the mutated file. Runner: `/usr/bin/python3 -B -X
pycache_prefix=/private/tmp/superheroes-pyc -m pytest … -q` (serial; the probe is not run under
`-n auto`).

## BP-VB-1 — the owner's verify command is elided from the fixer-emission lint text

**Axis:** an ordinary `{name}` token inside the owner's configured verify command must not refuse
the fixer emission, while the driver's own budget prose stays under the lint.

**Neutralization:** at `_order_lint_text`, make the budget-elision branch unreachable — the
condition `if (isinstance(budget, str) and budget.strip() …` becomes `if False and
(isinstance(budget, str) and budget.strip() …`.

**Red** — `plugins/superheroes/lib/tests/test_round_driver_order_lint.py::test_fixer_emission_elides_only_the_owner_verify_command_from_the_budget`
and `::test_fixer_emission_ignores_lint_triggers_inside_verify_command`:

```
E                   ValueError: order-render-refused:fixer-508e7896192355de:order-lint:order-placeholder-unfilled:item
_______ test_fixer_emission_ignores_lint_triggers_inside_verify_command ________
E                   ValueError: order-render-refused:fixer-508e7896192355de:order-lint:order-placeholder-unfilled:item
FAILED plugins/superheroes/lib/tests/test_round_driver_order_lint.py::test_fixer_emission_elides_only_the_owner_verify_command_from_the_budget
FAILED plugins/superheroes/lib/tests/test_round_driver_order_lint.py::test_fixer_emission_ignores_lint_triggers_inside_verify_command
2 failed in 4.85s
```

Both reds are raised by the **production emission path** (`_emit_orders_manifest` → the
`phase == P_FIXER` lint), not by a hand-built assertion — the refusal a real project would take.

**Restore:** restore the condition to `if (isinstance(budget, str) and budget.strip() …`.

**Restore receipt:**

```
$ git status --porcelain -- plugins/superheroes/lib/round_driver.py
(empty)
```

**Green:**

```
..                                                                       [100%]
2 passed in 4.98s
```

## Correction to the specimen named in the advisor's ruling

The ruling on #1272 (2026-09-20T11:5xZ) names this project's own verify command — which ends
`--base {baseRef}` — as the production specimen. **`baseRef` is exempt by construction:**
`order_lint._DRIVER_PH = frozenset({"baseRef"})` ("Driver-bound verify-command token — not an
unfilled order placeholder"), and `_placeholders` skips it. Measured: with every path in the
owner's command resolvable and `{baseRef}` its only brace token, the neutralized elision does
**not** refuse the emission.

The defect and the fix are unchanged — the elision was dead on the fixer phase — but the biting
specimen is **any non-exempt `{name}` token** in the owner's command (or a path in it that does
not resolve from the project's `repoRoot`), not `{baseRef}`. The proof above therefore uses a
project-shaped command that carries validator paths, `--base {baseRef}`, **and** an ordinary
`{item}` token; the `{item}` is what bites.
