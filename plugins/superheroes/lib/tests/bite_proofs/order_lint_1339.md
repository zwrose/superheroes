# order_lint bite-proof (issue #1339, WO-1)

**Provenance:** cursor composer-2.5 / dispatch-write (WO-1, issue #1339)

| ID | guarded element | proving test |
|---|---|---|
| BP-OL-1 | placeholder rule | `test_token_placeholder_unfilled` |
| BP-OL-2 | path rule, existence | `test_token_path_unresolved` |
| BP-OL-3 | path rule, escape | `test_symlink_escape_is_unresolved` |
| BP-OL-4 | result-shape rule | `test_token_result_shape_ambiguous` |
| BP-OL-5 | budget rule | `test_token_budget_missing_implementer` |
| BP-OL-6 | per-kind gate | `test_accepted_shape_fixer` |
| BP-OL-7 | unreadable mapping | `test_token_unreadable_missing_file` |
| BP-OL-8 | DoD planted bad path | `test_planted_bad_path_in_fixture_order` |

Normalization: `-B -X pycache_prefix=/private/tmp/superheroes-pyc-wo1`, single-node `::test_*`.

## BP-OL-1 — placeholder rule

**Axis:** `{{NAME}}` and `{name}` placeholders are detected and refused.

**Neutralization:** at `_placeholders`, insert `return [], 0` before the scan loop.

**Red** — `plugins/superheroes/lib/tests/test_order_lint.py::test_token_placeholder_unfilled`:

```
FAILED ... AssertionError: assert ('NAME' in details and 'foo' in details)
1 failed in 0.12s
```

**Restore:** remove the inserted `return [], 0` line.

**Green:** `1 passed in 0.12s`

## BP-OL-2 — path rule, existence

**Axis:** non-exempt path candidates must resolve under a root.

**Neutralization:** at `_resolve`, insert `return True, ""` before normpath logic.

**Red** — `::test_token_path_unresolved`:

```
FAILED ... AssertionError: assert False
1 failed in 0.18s
```

**Restore:** remove `return True, ""`.

**Green:** `1 passed in 0.12s`

## BP-OL-3 — path rule, escape

**Axis:** symlink targets outside the root are refused with `:escapes-root`.

**Neutralization:** replace the `rj != rr` realpath guard with `if False:`.

**Red** — `::test_symlink_escape_is_unresolved`:

```
FAILED ... AssertionError: assert False
1 failed in 0.14s
```

**Restore:** restore the `rj != rr and not rj.startswith(rr + os.sep)` guard.

**Green:** `1 passed in 0.13s`

## BP-OL-4 — result-shape rule

**Axis:** mixed stdout-report and native-typed literals are ambiguous.

**Neutralization:** at `_shape`, insert `return None` before family detection.

**Red** — `::test_token_result_shape_ambiguous`:

```
FAILED ... AssertionError: assert 'order-result-shape-ambiguous' in []
1 failed in 0.14s
```

**Restore:** remove `return None`.

**Green:** `1 passed in 0.12s`

## BP-OL-5 — budget rule

**Axis:** implementer orders must carry a budget signal.

**Neutralization:** `_budget_ok` body → `return True`.

**Red** — `::test_token_budget_missing_implementer`:

```
FAILED ... AssertionError: assert 'order-budget-missing' in []
1 failed in 0.15s
```

**Restore:** restore `_budget_ok` regex body.

**Green:** `1 passed in 0.13s`

## BP-OL-6 — per-kind gate

**Axis:** fixer kind skips the budget rule.

**Neutralization:** `if kind == "implementer"` → `if kind in KINDS`.

**Red** — `::test_accepted_shape_fixer`:

```
FAILED ... AssertionError: assert False is True
1 failed in 0.15s
```

**Restore:** restore `kind == "implementer"`.

**Green:** `1 passed in 0.12s`

## BP-OL-7 — unreadable mapping

**Axis:** `check` maps read failures to `order-unreadable`, never raises.

**Neutralization:** `except FileNotFoundError: return _refuse(...)` → `except FileNotFoundError: raise`.

**Red** — `::test_token_unreadable_missing_file`:

```
FileNotFoundError: [Errno 2] No such file or directory: '.../nope.md'
1 failed in 0.17s
```

**Restore:** restore the `_refuse` handler.

**Green:** `1 passed in 0.17s`

## BP-OL-8 — DoD planted bad path

**Axis:** with existence neutralized (BP-OL-2), a planted missing path is still caught when restore is in place; red proves the path rule bites.

**Neutralization:** same as BP-OL-2 (`return True, ""` at `_resolve`).

**Red** — `::test_planted_bad_path_in_fixture_order`:

```
FAILED ... AssertionError: assert False
1 failed in 0.15s
```

**Restore:** remove `return True, ""`.

**Green:** `1 passed in 0.12s`

## Appendix — `c11_l3_wo_a.md` findings at repository root

`repo_root` = repository root, `alt_roots=(plugins/superheroes,)`.

```json
{
  "ok": false,
  "kind": "implementer",
  "findings": [
    {"token": "order-path-unresolved", "detail": "plugins/superheroes/lib/conformance_probe.py"},
    {"token": "order-path-unresolved", "detail": "plugins/superheroes/lib/tests/test_conformance_probe.py"},
    {"token": "order-path-unresolved", "detail": "plugins/superheroes/lib/tests/bite_proofs/c11_l3_conformance_probe.md"},
    {"token": "order-path-unresolved", "detail": "lib/engine_result_channel.py"},
    {"token": "order-path-unresolved", "detail": "plugins/superheroes/lib/engine_result_channel.py"},
    {"token": "order-result-shape-ambiguous", "detail": "marker channel+\"resultKind\"+--output-schema"}
  ],
  "checked": {"paths": 13, "placeholders": 0}
}
```

Note: `engine_result_channel.py` is absent from this worktree; in a full tree where that file exists under `plugins/superheroes/lib/`, the last path finding would not fire at repository root.

## WO-2 — the driver hook

**Provenance:** cursor composer-2.5 / dispatch-write (WO-2, issue #1339)

| ID | guarded element | proving test |
|---|---|---|
| BP-OL-9 | the hook runs on the fixer phase | `test_fixer_emission_refuses_on_real_placeholder` |
| BP-OL-10 | the refusal carries the token | `test_fixer_emission_refuses_on_lint_finding` |
| BP-OL-11 | the guidance elision | `test_fixer_emission_ignores_lint_triggers_inside_gate_guidance` |

Normalization: `-B -X pycache_prefix=/private/tmp/superheroes-pyc-wo2`, single-node `::test_*`.

## BP-OL-9 — the hook runs on the fixer phase

**Axis:** `P_FIXER` emission runs `order_lint.check_text` before committing the manifest.

**Neutralization:** change `if phase == P_FIXER:` to `if False:`.

**Red** — `plugins/superheroes/lib/tests/test_round_driver_order_lint.py::test_fixer_emission_refuses_on_real_placeholder`:

```
FAILED ... AssertionError: Regex pattern did not match.
1 failed in ...
```

**Restore:** change `if False:` back to `if phase == P_FIXER:`.

**Green:** `1 passed in ...`

## BP-OL-10 — the refusal carries the token

**Axis:** a lint finding's token and detail appear in the `order-render-refused` string.

**Neutralization:** replace the raise's format with `"order-render-refused:%s:order-lint" % skey`.

**Red** — `plugins/superheroes/lib/tests/test_round_driver_order_lint.py::test_fixer_emission_refuses_on_lint_finding`:

```
FAILED ... AssertionError: Regex pattern did not match.
1 failed in ...
```

**Restore:** restore the original `raise ValueError("order-render-refused:%s:order-lint:%s" % (...))` format.

**Green:** `1 passed in ...`

## BP-OL-11 — the guidance elision

**Axis:** owner-gate guidance prose is elided from the fixer-emission lint text so quoted owner
paths, braces, or result-shape words never refuse emission.

**Neutralization:** set `lint_text = order_text` unconditionally (drop the `replace`).

**Red** — `plugins/superheroes/lib/tests/test_round_driver_order_lint.py::test_fixer_emission_ignores_lint_triggers_inside_gate_guidance`:

```
FAILED ... ValueError: order-render-refused:fixer-508e7896192355de:order-lint:...
1 failed in ...
```

**Restore:** restore `lint_text = order_text.replace(guidance, GATE_GUIDANCE_LINT_ELISION, 1)`.

**Green:** `1 passed in ...`
