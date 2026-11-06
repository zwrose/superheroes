# #2382 bite-proof — focus notes reach the scoped finder, or their absence is disclosed

Per-element bite-proof for `plugins/superheroes/lib/tests/test_focus_notes_reach_orders_2382.py` (`T` below). For each element the production code was neutralized with one targeted edit, the named node ran alone and went red on the guarded axis, and the edit was reverted by the inverse edit. The detectors were unedited throughout.

**Command** (red runs; the node id is the one in the table):

```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest <node> -q -p no:cacheprovider
```

**Output handling, said plainly.** G1, G3, G4 and G5 reds are the tail of the run's own output (truncated to the last lines, `cut -c1-300`). The G2, G6 and G7 reds were piped through `grep -E "^E  |^FAILED|passed|failed"` and so show the assertion (`E`) lines and the summary only, each line cut at 260–300 characters. Nothing below is reconstructed. No secrets or tokens appear; paths are the sandbox's pytest temp paths.

**Green.** After the last restore, one run of the whole file: `10 passed in 7.96s` (the nodes of all seven elements are inside it). Per-element green runs were not made one by one (command budget); the one combined run covers every node.

## G1 — `_order_placeholders` P_SCOPED `FOCUS_NOTES` entry (axis: notes reach the scoped order)

- **Neutralization:** deleted the line `"FOCUS_NOTES": _session_focus_notes(meta, cfg),` from the `P_SCOPED` branch (round_driver.py, now line 15253).
- **Node:** `T::test_t1_scoped_finder_order_carries_the_focus_notes`
- **Raw red (tail):**

```
>       assert "- Focus: check the fix order item 3" in text, text[:1500]
E       AssertionError: You are the [scoped finder](../glossary.md#scoped-finder) for a delta review round. ...
E         ## Input
E         ...
E         - Project conventions: CLAUDE.md at (this project has no CLAUDE.md at /tmp/claude-0/pytest-of-root/pytest-3/test_t1_scoped_finder_order_ca0), and the project profile.
E         
E         
E         ## Your assignment
E       assert '- Focus: check the fix order item 3' in 'You are the [scoped finder](../glossary.md#scoped-finder) for a delta review round. You scan only the **new surface**... `{"findings": [...]}` as your final response with nothing after it. Never write a landing file (read-only sandbox).\n'
FAILED plugins/superheroes/lib/tests/test_focus_notes_reach_orders_2382.py::test_t1_scoped_finder_order_carries_the_focus_notes
1 failed in 1.28s
```

- **Restore:** inverse edit put the line back. **Restore receipt:** grep shows `round_driver.py:15253:            "FOCUS_NOTES": _session_focus_notes(meta, cfg),`.

## G2 — `dispatch-scoped-finder.md` focus-line placeholder (axis: the template carries notes)

- **Neutralization:** deleted the placeholder line (line 12) after `- Project conventions: …`.
- **Nodes:** `T::test_t1_scoped_finder_order_carries_the_focus_notes` and `T::test_t4_carrying_phases_are_derived_from_the_templates`
- **Raw red (filtered to `E` lines and summary, see above):**

```
E       assert '- Focus: check the fix order item 3' in 'You are the [scoped finder](../glossary.md#scoped-finder) ...
E       AssertionError: {'dispatch-panel'}
E       assert {'dispatch-panel'} == {'dispatch-pa...coped-finder'}
E         Extra items in the right set:
E         'dispatch-scoped-finder'
FAILED plugins/superheroes/lib/tests/test_focus_notes_reach_orders_2382.py::test_t1_scoped_finder_order_carries_the_focus_notes
FAILED plugins/superheroes/lib/tests/test_focus_notes_reach_orders_2382.py::test_t4_carrying_phases_are_derived_from_the_templates
2 failed in 1.28s
```

- **Restore:** inverse edit re-added the line. **Restore receipt:** grep shows `dispatch-scoped-finder.md:12:` followed by the focus-line placeholder.

## G3 — `escape_placeholder_syntax` call in `focus_context_line` (axis: placeholder-syntax notes render)

- **Neutralization:** `return "- Focus: %s" % escape_placeholder_syntax(notes)` → `return "- Focus: %s" % notes`.
- **Node:** `T::test_t2_placeholder_syntax_in_notes_renders_escaped`
- **Raw red (tail):** the failure is at session setup, because the unescaped notes make the panel order refuse in `cmd_next`:

```
>       assert out["ok"], out
E       AssertionError: {'ok': False, 'reason': 'order-render-refused', 'detail': 'order-render-refused:architecture-reviewer-b784c838315fcad8:unknown-placeholder-remaining'}
E       assert False
FAILED plugins/superheroes/lib/tests/test_focus_notes_reach_orders_2382.py::test_t2_placeholder_syntax_in_notes_renders_escaped
1 failed in 0.49s
```

- **Restore:** inverse edit. **Restore receipt:** grep shows `round_orders.py:478:    return "- Focus: %s" % escape_placeholder_syntax(notes)`.

## G4 — `_disclose_focus_notes_not_carried` call in `_emit_orders_manifest` (axis: disclosure recorded)

- **Neutralization:** the call replaced by `pass`.
- **Node:** `T::test_t3_an_order_that_cannot_carry_the_notes_is_disclosed_on_the_round_and_receipt`
- **Raw red (tail):**

```
>       assert _round_rec(state).get("focusNotesNotCarried") == [
            {"phase": RD.P_VERIFIERS, "seats": [skey]}], _round_rec(state)
E       AssertionError: {'priorCommentsUnavailable': True}
E       assert None == [{'phase': 'dispatch-verifiers', 'seats': ['verifier-c1-3a4141b5fc43d922']}]
FAILED plugins/superheroes/lib/tests/test_focus_notes_reach_orders_2382.py::test_t3_an_order_that_cannot_carry_the_notes_is_disclosed_on_the_round_and_receipt
1 failed in 1.24s
```

- **Restore:** inverse edit. **Restore receipt:** grep shows `round_driver.py:15624:        _disclose_focus_notes_not_carried(state, phase, focus_uncarried)`.

## G5 — receipt line in `build_degraded_prose` (axis: the disclosure surfaces in the receipt)

- **Neutralization:** the `degraded_out.append(` of the `focus-notes-not-carried` line replaced by `_ = (` (the line is built and dropped).
- **Node:** `T::test_t3_an_order_that_cannot_carry_the_notes_is_disclosed_on_the_round_and_receipt` (its round-record half passes; its receipt half goes red)
- **Raw red (tail):**

```
>       assert len(lines) == 1, degraded
E       AssertionError: ['seat-map constraint breach: critical-diversity, maker-family (seat code-reviewer), maker-family (seat premortem-revi... — panel ran without prior PR comments; any claim that prior comments were considered is not supported for this round']
E       assert 0 == 1
FAILED plugins/superheroes/lib/tests/test_focus_notes_reach_orders_2382.py::test_t3_an_order_that_cannot_carry_the_notes_is_disclosed_on_the_round_and_receipt
1 failed in 1.26s
```

- **Restore:** inverse edit. **Restore receipt:** grep shows `receipt_disclosures.py:700:                degraded_out.append(` immediately before `"focus-notes-not-carried (round %s): …`.

## G6 — "notes non-empty" condition in the emission check (axis: no notes, no disclosure)

- **Neutralization:** `if session_focus and round_orders.order_carries_focus(…)` → `if True and round_orders.order_carries_focus(…)`.
- **Node:** `T::test_t5_no_focus_notes_changes_nothing` (all three params: `None`, `""`, whitespace only, so edge E1 is inside the proof)
- **Raw red (filtered to `E` lines and summary, see above):**

```
E       AssertionError: {'priorCommentsUnavailable': True, 'focusNotesNotCarried': [{'phase': 'dispatch-verifiers', 'seats': ['verifier-c1-3a4141b5fc43d922']}]}
E       assert 'focusNotesNotCarried' not in {'priorCommentsUnavailable': True, 'focusNotesNotCarried': [{'phase': 'dispatch-verifiers', 'seats': ['verifier-c1-3a4141b5fc43d922']}]}
   (the same pair of lines for each of the three params)
FAILED plugins/superheroes/lib/tests/test_focus_notes_reach_orders_2382.py::test_t5_no_focus_notes_changes_nothing[None]
FAILED plugins/superheroes/lib/tests/test_focus_notes_reach_orders_2382.py::test_t5_no_focus_notes_changes_nothing[]
FAILED plugins/superheroes/lib/tests/test_focus_notes_reach_orders_2382.py::test_t5_no_focus_notes_changes_nothing[   \n\t ]
3 failed in 3.47s
```

- **Restore:** inverse edit. **Restore receipt:** grep shows `round_driver.py:15595:        if session_focus and round_orders.order_carries_focus(phase, context)[0] is not True:`.

## G7 — merge in `_disclose_focus_notes_not_carried` (axis: an earlier row survives)

- **Neutralization:** `merged = [dict(row) for row in prior if isinstance(row, dict)] if isinstance(prior, list) else []` → `merged = []` (overwrite).
- **Node:** `T::test_t6_a_phase_emitted_twice_in_a_round_unions_its_seats_and_keeps_earlier_rows`
- **Raw red (filtered to `E` lines and summary, see above):**

```
E       AssertionError: [{'phase': 'dispatch-verifiers', 'seats': ['verifier-c2-bcf88f46b431afe9']}]
E       assert 1 == 2
E        +  where 1 = len({'dispatch-verifiers': {'phase': 'dispatch-verifiers', 'seats': ['verifier-c2-bcf88f46b431afe9']}})
FAILED plugins/superheroes/lib/tests/test_focus_notes_reach_orders_2382.py::test_t6_a_phase_emitted_twice_in_a_round_unions_its_seats_and_keeps_earlier_rows
1 failed in 1.56s
```

- **Restore:** inverse edit. **Restore receipt:** grep shows `round_driver.py:14366:    merged = [dict(row) for row in prior if isinstance(row, dict)] if isinstance(prior, list) else []`.

## Not proven

- `order_carries_focus`'s read-failure leg (edge E2): T4b covers an unknown phase (no template file), not an unreadable one; no neutralization was run for it.
- `test_e3_a_malformed_row_is_skipped_by_the_receipt_never_raised` (edge E3) has no neutralization run; it was not in the declared set.
