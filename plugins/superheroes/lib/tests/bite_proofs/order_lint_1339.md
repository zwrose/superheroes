# order_lint bite-proof (issue #1339, WO-1)

**Provenance:** cursor composer-2.5 / dispatch-write (WO-1, issue #1339)

| ID | guarded element | proving test |
|---|---|---|
| BP-OL-1 | placeholder rule | `test_token_placeholder_unfilled` |
| BP-OL-2 | path rule, existence | `test_token_path_unresolved` |
| BP-OL-3 | path rule, escape | `test_symlink_escape_is_unresolved` |
| BP-OL-4 | result-shape rule | `test_result_shape_ambiguous_fires_on_stdout_protocol_literals` |
| BP-OL-5 | budget rule | `test_token_budget_missing_implementer` |
| BP-OL-6 | per-kind gate | `test_accepted_shape_fixer` |
| BP-OL-7 | unreadable mapping | `test_token_unreadable_missing_file` |
| BP-OL-8 | DoD planted bad path | `test_planted_bad_path_in_fixture_order` |

Normalization: `-B -X pycache_prefix=/private/tmp/superheroes-pyc-wo1`, single-node `::test_*`.
Every proof below was re-run by the auto-fix round; each neutralization was reverted by its inverse
edit with post-restore `git status --porcelain` over the neutralized path.


## BP-OL-1 — placeholder rule

**Axis:** `{{NAME}}` and `{name}` placeholders are detected and refused.

**Neutralization:** at `_placeholders`, insert `return [], 0` before the scan loop.

**Red** — `plugins/superheroes/lib/tests/test_order_lint.py::test_token_placeholder_unfilled`:

```
=================================== FAILURES ===================================
_______________________ test_token_placeholder_unfilled ________________________
plugins/superheroes/lib/tests/test_order_lint.py:111: in test_token_placeholder_unfilled
    assert "NAME" in details and "foo" in details
E   AssertionError: assert ('NAME' in [])
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_order_lint.py::test_token_placeholder_unfilled
1 failed in 0.20s
```

**Restore:** remove the inserted `return [], 0` line.

**Restore receipt:**
```
$ git status --porcelain -- plugins/superheroes/lib/order_lint.py
(empty)
```

**Green:**

```
1 passed in 0.18s
```

## BP-OL-2 — path rule, existence

**Axis:** non-exempt path candidates must resolve under a root.

**Neutralization:** at `_resolve`, insert `return True, ""` before normpath logic.

**Red** — `::test_token_path_unresolved`:

```
=================================== FAILURES ===================================
__________________________ test_token_path_unresolved __________________________
plugins/superheroes/lib/tests/test_order_lint.py:99: in test_token_path_unresolved
    assert any(
E   assert False
E    +  where False = any(<generator object test_token_path_unresolved.<locals>.<genexpr> at 0x1021bb890>)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_order_lint.py::test_token_path_unresolved
1 failed in 0.18s
```

**Restore:** remove `return True, ""`.

**Restore receipt:**
```
$ git status --porcelain -- plugins/superheroes/lib/order_lint.py
(empty)
```

**Green:**

```
1 passed in 0.17s
```

## BP-OL-3 — path rule, escape

**Axis:** symlink targets outside the root are refused with `:escapes-root`.

**Neutralization:** replace the `rj != rr` realpath guard with `if False:`.

**Red** — `::test_symlink_escape_is_unresolved`:

```
=================================== FAILURES ===================================
______________________ test_symlink_escape_is_unresolved _______________________
plugins/superheroes/lib/tests/test_order_lint.py:317: in test_symlink_escape_is_unresolved
    assert any("escapes-root" in d for d in _details(r))
E   assert False
E    +  where False = any(<generator object test_symlink_escape_is_unresolved.<locals>.<genexpr> at 0x1060acdd0>)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_order_lint.py::test_symlink_escape_is_unresolved
1 failed in 0.18s
```

**Restore:** restore the `rj != rr and not rj.startswith(rr + os.sep)` guard.

**Restore receipt:**
```
$ git status --porcelain -- plugins/superheroes/lib/order_lint.py
(empty)
```

**Green:**

```
1 passed in 0.15s
```

## BP-OL-4 — result-shape rule

**Axis:** write-report sentinel beside a native-typed literal, or fixer literal with expect-items.

**Neutralization:** at `_shape`, insert `return None` before family detection.

**Red** — `::test_result_shape_ambiguous_fires_on_stdout_protocol_literals`:

```
=================================== FAILURES ===================================
________ test_result_shape_ambiguous_fires_on_stdout_protocol_literals _________
plugins/superheroes/lib/tests/test_order_lint.py:476: in test_result_shape_ambiguous_fires_on_stdout_protocol_literals
    assert OL.TOKEN_RESULT_SHAPE_AMBIGUOUS in _tokens(r), marker
E   AssertionError: <<<SUPERHEROES-WRITE-REPORT>>>
E   assert 'order-result-shape-ambiguous' in []
E    +  where 'order-result-shape-ambiguous' = OL.TOKEN_RESULT_SHAPE_AMBIGUOUS
E    +  and   [] = _tokens({'checked': {'paths': 0, 'placeholders': 0}, 'findings': [], 'kind': 'implementer', 'ok': True, ...})
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_order_lint.py::test_result_shape_ambiguous_fires_on_stdout_protocol_literals
1 failed in 0.18s
```

**Restore:** remove `return None`.

**Restore receipt:**
```
$ git status --porcelain -- plugins/superheroes/lib/order_lint.py
(empty)
```

**Green:**

```
1 passed in 0.15s
```

## BP-OL-5 — budget rule

**Axis:** implementer orders must carry a budget signal.

**Neutralization:** `_budget_ok` body → `return True`.

**Red** — `::test_token_budget_missing_implementer`:

```
=================================== FAILURES ===================================
____________________ test_token_budget_missing_implementer _____________________
plugins/superheroes/lib/tests/test_order_lint.py:130: in test_token_budget_missing_implementer
    assert OL.TOKEN_BUDGET_MISSING in _tokens(r)
E   AssertionError: assert 'order-budget-missing' in []
E    +  where 'order-budget-missing' = OL.TOKEN_BUDGET_MISSING
E    +  and   [] = _tokens({'checked': {'paths': 1, 'placeholders': 0}, 'findings': [], 'kind': 'implementer', 'ok': True, ...})
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_order_lint.py::test_token_budget_missing_implementer
1 failed in 0.15s
```

**Restore:** restore `_budget_ok` regex body.

**Restore receipt:**
```
$ git status --porcelain -- plugins/superheroes/lib/order_lint.py
(empty)
```

**Green:**

```
1 passed in 0.16s
```

## BP-OL-6 — per-kind gate

**Axis:** fixer kind skips the budget rule.

**Neutralization:** `if kind == "implementer"` → `if kind in KINDS`.

**Red** — `::test_accepted_shape_fixer`:

```
=================================== FAILURES ===================================
__________________________ test_accepted_shape_fixer ___________________________
plugins/superheroes/lib/tests/test_order_lint.py:170: in test_accepted_shape_fixer
    assert r["ok"] is True
E   assert False is True
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_order_lint.py::test_accepted_shape_fixer
1 failed in 0.19s
```

**Restore:** restore `kind == "implementer"`.

**Restore receipt:**
```
$ git status --porcelain -- plugins/superheroes/lib/order_lint.py
(empty)
```

**Green:**

```
1 passed in 0.16s
```

## BP-OL-7 — unreadable mapping

**Axis:** `check` maps read failures to `order-unreadable`, never raises.

**Neutralization:** `except FileNotFoundError: return _refuse(...)` → `except FileNotFoundError: raise`.

**Red** — `::test_token_unreadable_missing_file`:

```
=================================== FAILURES ===================================
______________________ test_token_unreadable_missing_file ______________________
plugins/superheroes/lib/tests/test_order_lint.py:74: in test_token_unreadable_missing_file
    r = _record(OL.check(str(tmp_path / "nope.md"), str(tmp_path)))
plugins/superheroes/lib/order_lint.py:305: in check
    with open(order_path, encoding="utf-8", errors="strict") as fh:
E   FileNotFoundError: [Errno 2] No such file or directory: '/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-1449/test_token_unreadable_missing_0/nope.md'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_order_lint.py::test_token_unreadable_missing_file
1 failed in 0.19s
```

**Restore:** restore the `_refuse` handler.

**Restore receipt:**
```
$ git status --porcelain -- plugins/superheroes/lib/order_lint.py
(empty)
```

**Green:**

```
1 passed in 0.23s
```

## BP-OL-8 — DoD planted bad path

**Axis:** with existence neutralized (BP-OL-2), a planted missing path is still caught when restore is in place; red proves the path rule bites.

**Neutralization:** same as BP-OL-2 (`return True, ""` at `_resolve`).

**Red** — `::test_planted_bad_path_in_fixture_order`:

```
=================================== FAILURES ===================================
____________________ test_planted_bad_path_in_fixture_order ____________________
plugins/superheroes/lib/tests/test_order_lint.py:398: in test_planted_bad_path_in_fixture_order
    assert any("does_not_exist_1339.py" in d for d in _details(r))
E   assert False
E    +  where False = any(<generator object test_planted_bad_path_in_fixture_order.<locals>.<genexpr> at 0x10462f890>)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_order_lint.py::test_planted_bad_path_in_fixture_order
1 failed in 0.29s
```

**Restore:** remove `return True, ""`.

**Restore receipt:**
```
$ git status --porcelain -- plugins/superheroes/lib/order_lint.py
(empty)
```

**Green:**

```
1 passed in 0.26s
```

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
| BP-OL-12 | the residuals elision | `test_fixer_emission_ignores_lint_triggers_inside_ratified_residuals` |
| BP-OL-13 | the plugin alt-root | `test_fixer_emission_resolves_plugin_relative_citation_via_plugin_root` |

Normalization: `-B -X pycache_prefix=/private/tmp/superheroes-pyc-wo2`, single-node `::test_*`.
Every proof below was re-run by the auto-fix round; each neutralization was reverted by its inverse
edit with post-restore `git status --porcelain` over the neutralized path.


## BP-OL-9 — the hook runs on the fixer phase

**Axis:** `P_FIXER` emission runs `order_lint.check_text` before committing the manifest.

**Neutralization:** change `if phase == P_FIXER:` to `if False:`.

**Red** — `plugins/superheroes/lib/tests/test_round_driver_order_lint.py::test_fixer_emission_refuses_on_real_placeholder`:

```
=================================== FAILURES ===================================
_______________ test_fixer_emission_refuses_on_real_placeholder ________________
plugins/superheroes/lib/tests/test_round_driver_order_lint.py:159: in test_fixer_emission_refuses_on_real_placeholder
    _emit_fixer(session_dir, state)
E   Failed: DID NOT RAISE <class 'ValueError'>
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_driver_order_lint.py::test_fixer_emission_refuses_on_real_placeholder
1 failed in 6.40s
```

**Restore:** change `if False:` back to `if phase == P_FIXER:`.

**Restore receipt:**
```
$ git status --porcelain -- plugins/superheroes/lib/round_driver.py
(empty)
```

**Green:**

```
1 passed in 6.52s
```

## BP-OL-10 — the refusal carries the token

**Axis:** a lint finding's token and detail appear in the `order-render-refused` string.

**Neutralization:** replace the raise's format with `"order-render-refused:%s:order-lint" % skey`.

**Red** — `plugins/superheroes/lib/tests/test_round_driver_order_lint.py::test_fixer_emission_refuses_on_lint_finding`:

```
=================================== FAILURES ===================================
_________________ test_fixer_emission_refuses_on_lint_finding __________________
plugins/superheroes/lib/tests/test_round_driver_order_lint.py:147: in test_fixer_emission_refuses_on_lint_finding
    _emit_fixer(session_dir, state)
plugins/superheroes/lib/tests/test_round_driver_order_lint.py:94: in _emit_fixer
    return RD._emit_orders_manifest(
plugins/superheroes/lib/round_driver.py:6774: in _emit_orders_manifest
    raise ValueError("order-render-refused:%s:order-lint" % skey)
E   ValueError: order-render-refused:fixer-508e7896192355de:order-lint

During handling of the above exception, another exception occurred:
plugins/superheroes/lib/tests/test_round_driver_order_lint.py:147: in test_fixer_emission_refuses_on_lint_finding
    _emit_fixer(session_dir, state)
E   AssertionError: Regex pattern did not match.
E    Regex: 'order-render-refused:fixer-508e7896192355de:order-lint:order-placeholder-unfilled:FOO'
E    Input: 'order-render-refused:fixer-508e7896192355de:order-lint'
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_driver_order_lint.py::test_fixer_emission_refuses_on_lint_finding
1 failed in 6.52s
```

**Restore:** restore the original `raise ValueError("order-render-refused:%s:order-lint:%s" % (...))` format.

**Restore receipt:**
```
$ git status --porcelain -- plugins/superheroes/lib/round_driver.py
(empty)
```

**Green:**

```
1 passed in 6.66s
```

## BP-OL-11 — the guidance elision

**Axis:** owner-gate guidance prose is elided from the fixer-emission lint text so quoted owner
paths, braces, or result-shape words never refuse emission.

**Neutralization:** at `_order_lint_text`, drop `ph.get("GATE_GUIDANCE")` from the quoted tuple.

**Red** — `plugins/superheroes/lib/tests/test_round_driver_order_lint.py::test_fixer_emission_ignores_lint_triggers_inside_gate_guidance`:

```
=================================== FAILURES ===================================
________ test_fixer_emission_ignores_lint_triggers_inside_gate_guidance ________
plugins/superheroes/lib/tests/test_round_driver_order_lint.py:228: in test_fixer_emission_ignores_lint_triggers_inside_gate_guidance
    anchor = _emit_fixer(session_dir, state)
plugins/superheroes/lib/tests/test_round_driver_order_lint.py:94: in _emit_fixer
    return RD._emit_orders_manifest(
plugins/superheroes/lib/round_driver.py:6774: in _emit_orders_manifest
    raise ValueError("order-render-refused:%s:order-lint:%s" % (
E   ValueError: order-render-refused:fixer-508e7896192355de:order-lint:order-path-unresolved:plugins/superheroes/lib/no_such_file_1339.py
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_driver_order_lint.py::test_fixer_emission_ignores_lint_triggers_inside_gate_guidance
1 failed in 6.63s
```

**Restore:** restore `ph.get("GATE_GUIDANCE")` in the `_order_lint_text` quoted tuple.

**Restore receipt:**
```
$ git status --porcelain -- plugins/superheroes/lib/round_driver.py
(empty)
```

**Green:**

```
1 passed in 6.29s
```

## BP-OL-12 — the residuals elision

**Axis:** ratified-residuals quoted data is elided from the fixer-emission lint text so owner
paths, braces, or result-shape words in the residuals block never refuse emission.

**Neutralization:** at `_order_lint_text`, drop `context.get("ratified_residuals")` from the
quoted tuple.

**Red** — `plugins/superheroes/lib/tests/test_round_driver_order_lint.py::test_fixer_emission_ignores_lint_triggers_inside_ratified_residuals`:

```
=================================== FAILURES ===================================
_____ test_fixer_emission_ignores_lint_triggers_inside_ratified_residuals ______
plugins/superheroes/lib/tests/test_round_driver_order_lint.py:265: in test_fixer_emission_ignores_lint_triggers_inside_ratified_residuals
    anchor = _emit_fixer(session_dir, state)
plugins/superheroes/lib/tests/test_round_driver_order_lint.py:94: in _emit_fixer
    return RD._emit_orders_manifest(
plugins/superheroes/lib/round_driver.py:6774: in _emit_orders_manifest
    raise ValueError("order-render-refused:%s:order-lint:%s" % (
E   ValueError: order-render-refused:fixer-508e7896192355de:order-lint:order-path-unresolved:lib/tests/no_such_residual_file_1339.py
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_driver_order_lint.py::test_fixer_emission_ignores_lint_triggers_inside_ratified_residuals
1 failed in 6.13s
```

**Restore:** restore `context.get("ratified_residuals")` in the `_order_lint_text` quoted tuple.

**Restore receipt:**
```
$ git status --porcelain -- plugins/superheroes/lib/round_driver.py
(empty)
```

**Green:**

```
1 passed in 5.59s
```

## BP-OL-13 — the plugin alt-root

**Axis:** driver-authored plugin-relative citations resolve via the plugin root at fixer emission.

**Neutralization:** pass `alt_roots=()` to `order_lint.check_text` in the `P_FIXER` block.

**Red** — `plugins/superheroes/lib/tests/test_round_driver_order_lint.py::test_fixer_emission_resolves_plugin_relative_citation_via_plugin_root`:

```
=================================== FAILURES ===================================
____ test_fixer_emission_resolves_plugin_relative_citation_via_plugin_root _____
plugins/superheroes/lib/tests/test_round_driver_order_lint.py:283: in test_fixer_emission_resolves_plugin_relative_citation_via_plugin_root
    anchor = _emit_fixer(session_dir, state)
plugins/superheroes/lib/tests/test_round_driver_order_lint.py:94: in _emit_fixer
    return RD._emit_orders_manifest(
plugins/superheroes/lib/round_driver.py:6774: in _emit_orders_manifest
    raise ValueError("order-render-refused:%s:order-lint:%s" % (
E   ValueError: order-render-refused:fixer-508e7896192355de:order-lint:order-path-unresolved:rubric/review-base.md
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_driver_order_lint.py::test_fixer_emission_resolves_plugin_relative_citation_via_plugin_root
1 failed in 6.57s
```

**Restore:** restore `alt_roots=(_plugin_resource_root(),)` in the `P_FIXER` block.

**Restore receipt:**
```
$ git status --porcelain -- plugins/superheroes/lib/round_driver.py
(empty)
```

**Green:**

```
1 passed in 7.48s
```


## The semantic half — recorded seat runs (orchestrator, 2026-09-19)

**Provenance:** the workhorse orchestrator (Claude Opus 5) dispatching the semantic seat as a native
subagent at the `mechanical` role's registry cell (`haiku-4.5`, effort `medium`; `dispatch_guard.py
check` exit 0), prompt = `rubric/orders/order-lint-semantic.md` at head `0feff589` plus the two
trailing lines naming the order and the repository root. The seat is a detector with no code to
neutralize: its bite-proof is a planted-defect order it must flag (red) beside a clean twin it must
pass (green), plus the real C11 layer 3 specimen the deterministic half cannot catch. The
deterministic half returns `{"ok": true, "findings": []}` on all three orders (run at head), so what
fires below is the semantic seat alone. Local paths are the session's scratch directory, kept as
written; nothing sensitive is in them.

| ID | guarded element | axis | order | result |
|---|---|---|---|---|
| BP-OL-14 | item (b) — contradictory paragraphs; item (a) — duplicated items | a planted order carrying two budgets (4 vs 9 invocations) and two contradictory `check_text` contracts (raise vs never-raise) is flagged Important | `planted-semantic-order.md` (session scratch) | **red**: 2 Important findings, 29 s wall, 4 tool uses |
| BP-OL-14 (green) | the same seat on the clean twin | the twin with the duplicate and the contradiction removed is passed | `clean-semantic-order.md` (session scratch) | **green**: 0 findings, non-empty `investigated`, 50 s wall, 6 tool uses |
| BP-OL-15 | item (d) — dictated build provenance on a shipped surface | C11 layer 3's WO-C (the WO-C2 rework's cause: "did not pass its trial" dictated into `dispatch-mechanics.md`) is flagged Important | `lib/tests/fixtures/order_lint/c11_l3_wo_c.md` | **red (caught)**: 1 Important finding, 84 s wall, 15 tool uses |

### BP-OL-14 — raw red (planted order)

```json
{"findings": [
 {"severity": "Important", "title": "Contradictory requirements for check_text behavior",
  "body": "Item 4 demands: 'Change `check_text` so that an unknown `kind` value raises `ValueError` immediately — a caller that passes a bad kind should see the exception, never a result dict.' Item 5 demands: '`check_text` must keep its never-raises contract: every failure, including an unknown `kind`, maps to a finding token and a result dict; the function never raises.' These requirements are mutually exclusive.",
  "paragraph": "Item 4 — the module's public entry and Item 5 — the never-raises contract"},
 {"severity": "Important", "title": "Conflicting budget constraints",
  "body": "Item 1 states: 'Run at most 4 command invocations in total; the two pytest runs sit inside that budget.' Item 3 contradicts this: 'You may spend up to 9 command invocations; the budget is generous because the suite is slow.' The Commands section reiterates 'budget: at most 4 invocations' matching Item 1, creating ambiguity about which constraint applies.",
  "paragraph": "Item 1 — the budget and Item 3 — the budget, restated"}],
 "investigated": ["/tmp/review-KbCr0yBV/planted-semantic-order.md", "/tmp/review-KbCr0yBV/semantic-prompt-head.md", ".../plugins/superheroes/lib/order_lint.py", ".../plugins/superheroes/lib/tests/test_order_lint.py"]}
```

### BP-OL-14 — raw green (clean twin)

```json
{"findings": [], "investigated": ["/tmp/review-KbCr0yBV/clean-semantic-order.md", ".../plugins/superheroes/lib/order_lint.py", ".../plugins/superheroes/agents/implementer.md", ".../plugins/superheroes/lib/tests/test_order_lint.py"]}
```

### BP-OL-15 — raw red (C11 layer 3 WO-C, the WO-C2 rework's cause)

```json
{"findings": [{"severity": "Important", "title": "Order directs prose provenance to shipped surfaces, violating R29",
  "body": "Item 1(b) orders adding to dispatch-mechanics.md: 'which is why the native move for cursor did not pass its trial' — a past trial outcome. Item 2 orders adding to TRANSITION.md: 'the two-dispatch trial's write dispatch validated, the review dispatch did not' — references to past experimental results. Both are project provenance forbidden by R29 (prose-standard.md \":210\"). The order cites R29 but then directs violations of it.",
  "paragraph": "Item 1(b) and Item 2: prose provisions"}],
 "investigated": [".../plugins/superheroes/lib/tests/fixtures/order_lint/c11_l3_wo_c.md", ".../plugins/superheroes/rubric/prose-standard.md"]}
```

The planted order and its clean twin are session scratch (the deterministic half's `check` on both:
`{"ok": true, "findings": []}`); they are quoted here in full by their defects — two budgets, two
`check_text` contracts — rather than committed as fixtures, because a fixture the seat has seen
in the repository is not a control. The `...` in `investigated` elides the worktree's absolute
prefix only.
