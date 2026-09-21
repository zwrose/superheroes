# order_lint inlined-template mask bite-proof (issue #1373)

**Provenance:** orchestrator-typed (light lane), claude Opus 5; proofs run by the same session in a
detached probe worktree at `c0c24240` (plus the E2 fixture fix below).

Guarded-element set, declared before review:

| ID | guarded element | axis | proving test(s) |
|---|---|---|---|
| E1 | `order_lint.mask_template` masks a verbatim template copy | a charter-shaped order is not refused for the template's own examples | `test_charter_shaped_order_passes_cli`, `test_fixer_door_passes_charter_shaped_order` |
| E2 | the mask covers the verbatim template only | a placeholder planted in an altered copy still refuses | `test_placeholder_planted_in_an_altered_template_copy_refuses` |
| E3 | text around the template is still graded | an authored placeholder refuses, named by its own name | `test_authored_placeholder_refuses_and_names_the_authored_line`, `test_fixer_door_refuses_authored_placeholder` |
| E4 | unreadable template ⇒ nothing masked | the order is graded whole (fail closed) | `test_unreadable_template_masks_nothing` |
| E5 | `round_driver._order_lint_text` masks before its quoted-data elision | the fixer door grades the template like the CLI | `test_fixer_door_passes_charter_shaped_order` |

Normalization: `-B -X pycache_prefix=/private/tmp/superheroes-pyc-1373-probe -p no:cacheprovider`,
single-node `::test_*` selection. Every neutralization was applied and reverted by targeted edits;
the restore receipt for each is `git status --porcelain` / `git diff --stat` over the neutralized
source file showing it clean (the only other dirty path in the probe tree was the E2 fixture fix,
mirrored from the build branch).

## E1 — verbatim copy is masked

**Neutralization:** in `mask_template`, `n = text.count(body) if body else 0` → `n = 0`.

**Red:**
```
E       AssertionError: assert (1, False, [{...unresolved'}]) == (0, True, [])
E                   ValueError: order-render-refused:fixer-508e7896192355de:order-lint:order-placeholder-unfilled:NAME
FAILED ...::test_charter_shaped_order_passes_cli
FAILED ...::test_fixer_door_passes_charter_shaped_order
2 failed in 2.09s
```

**Restore:** inverse edit. **Restore receipt:** `order_lint.py` absent from `git status --porcelain`.

**Green:** `2 passed in 2.10s`

## E2 — only a verbatim copy is masked

**Neutralization:** a too-wide mask anchored on the template's opening line — inserted before the
count line:
```
    if body and body.splitlines()[0] in text:
        return text[:text.index(body.splitlines()[0])], 1
```

**First run was green — a fixture defect, fixed in the fixture, assertion unchanged.** The plant
(`exactly one` → `exactly {{COUNT}}`) sat on the template's first line, so the opening-anchored mask
never matched and the probe could not discriminate (vacuity trap 4, second face). The plant moved
mid-template (`## Validating your work order` → `## Validating your {{COUNT}} work order`), and the
test now asserts the first four lines are untouched so the fixture keeps creating the condition.

**Red (fixed fixture):**
```
E       assert True is False
FAILED ...::test_placeholder_planted_in_an_altered_template_copy_refuses
1 failed in 0.14s
```

**Restore:** inverse edit. **Restore receipt:** `order_lint.py` absent from `git status --porcelain`.

**Green:** `1 passed in 0.14s`

## E3 — authored text is still graded

**Neutralization:** in `mask_template`, `text = text.replace(body, "\n" * (body.count("\n") + 2))`
→ `text = "\n"` (the mask swallows the authored text too).

**Red:**
```
E         At index 0 diff: {'token': 'order-budget-missing', 'detail': ''} != {'token': 'order-placeholder-unfilled', 'detail': 'TARGET_FILE'}
E           - int:order-unreadable:empty
E           + int:order-placeholder-unfilled:TARGET_FILE
FAILED ...::test_authored_placeholder_refuses_and_names_the_authored_line
FAILED ...::test_fixer_door_refuses_authored_placeholder
2 failed in 2.06s
```

**Restore:** inverse edit. **Restore receipt:** `order_lint.py` absent from `git status --porcelain`.

**Green:** `2 passed in 10.52s`

## E4 — unreadable template masks nothing

**Neutralization:** fall open on an unreadable template — inserted after `body = _template_body()`:
```
    if body is None:
        return "", 0
```

**Red:**
```
E       AssertionError: assert {'detail': 'NAME', 'token': 'order-placeholder-unfilled'} in [{'detail': '', 'token': 'order-budget-missing'}]
FAILED ...::test_unreadable_template_masks_nothing
1 failed in 0.58s
```

**Restore:** inverse edit. **Restore receipt:** `order_lint.py` absent from `git status --porcelain`.

**Green:** `1 passed in 0.56s`

## E5 — the fixer door masks before elision

**Neutralization:** in `round_driver._order_lint_text`, `text, _ = order_lint.mask_template(order_text)`
→ `text = order_text` (the verify-command value `none` is then elided inside the template body,
so the copy is no longer verbatim).

**Red:**
```
E                   ValueError: order-render-refused:fixer-508e7896192355de:order-lint:order-placeholder-unfilled:NAME
FAILED ...::test_fixer_door_passes_charter_shaped_order
1 failed in 9.66s
```

**Restore:** inverse edit. **Restore receipt:** `git diff --stat -- plugins/superheroes/lib/order_lint.py
plugins/superheroes/lib/round_driver.py` empty.

**Green:** `1 passed in 2.47s`
