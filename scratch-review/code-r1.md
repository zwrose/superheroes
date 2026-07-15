# Code review — fix/superheroes-430-synthesis-fold (r1)

Dimension: Code (correctness). Base: origin/main @ 515e0c1.

## Verdict: no blocking findings. One Minor twin-parity divergence.

## Findings

### Minor — `unmatched` array ordering can diverge between the Python and JS twins (CONVENTIONS §11)
`plugins/superheroes/lib/loop_synthesis.js:51` vs `plugins/superheroes/lib/loop_synthesis.py:110`

The two twins build `unmatched` differently:
- Python: `unmatched = [vid for vid in by_id if vid not in matched_ids]` — iterates a `dict` in **insertion order** for all keys.
- JS: `Object.keys(byId).filter((vid) => !matchedIds[vid])` — `Object.keys` on the `Object.create(null)` map returns **integer-like string keys first (ascending numeric order)**, then the remaining string keys in insertion order.

For the normal panel case this never triggers: staged/verdict ids are `file::normalized-title`, always contain `::`, and are never integer-like, so insertion order is preserved on both sides. But `by_id`/`byId` is keyed on **model-produced verdict ids**, and `unmatched` is precisely the channel that captures a *drifted/mis-keyed* verdict id — an id the model invented. If such a drifted id is a pure integer string (e.g. `"42"`) alongside normal `file::title` ids, JS hoists it to the front of `unmatched` while Python keeps first-seen order. The two implementations then emit different `unmatched` orderings for identical input.

Impact is bounded: membership of `unmatched` is identical on both sides (only order differs), and no gate/terminal/confirmation decision reads the order — it feeds only the readout's loud-disclosure list and the round record. So this is not a correctness/decision defect. But it is a genuine §11 byte-parity divergence in newly-added code, and the `parity/loop_synthesis/consume/*.json` harness compares `consume` output exactly — a future fixture with a numeric drifted verdict id would fail parity. No existing fixture exercises a numeric id, so CI is green today.

Suggestion: make the JS side track first-seen insertion order explicitly rather than relying on `Object.keys` (which reorders integer-like keys). For example, push each newly-seen `v.id` into an `order` array as `byId` is populated, then `const unmatched = order.filter((vid) => !matchedIds[vid])`. That reproduces Python `dict` insertion order for every key shape.

## Areas verified clean (asked focus)

- **Staged id makes the match succeed.** `review_panel_shell.js:794-796` stages `f.id = circuitBreaker.findingIdentity(f)` on the `compiled` copies before the leaf; the judge echoes it verbatim (showrunner.js:633-635 code leaf, :781-784 doc leaf). `consume` recomputes `identity = findingIdentity(f)` on the same finding (loop_synthesis.js:26 / .py:81) and matches `byId[identity]`. Since staged `f.id == findingIdentity(f) == verdict.id`, the *primary* identity match succeeds; the `f.id` fallback is redundant-but-consistent (== identity). No path where staging breaks a match.
- **No downstream leak from mutating `compiled`.** `compileDimensionResults` (panel_tally.js:125-140) and `compileFindings` (:19-41) return `Object.assign({}, f)` copies, so the `compiled` findings are fresh objects, not references into `roundFindings`. `graftSynthesizedFindings` (:819-855) rekeys on `findingIdentity(...)` recomputed (not the staged id) and builds `enriched` from the *original* `roundFindings` findings, so the staged `id` never propagates to grafted findings, panel_tally, or the round-gate path (`roundGateFromDimensionResults` recompiles from `roundFindings`). `collectRoundUsage` uses `synthesized.usage`, not findings. Clobbering any pre-existing reviewer `id` is intended (native panels key on identity) and harmless.
- **matched-key / fallback bookkeeping parity.** Both twins: primary key = `identity` when `byId[identity]` present, else fallback to `f.id`; `matched_ids` records the actual matched key; drop/downgrade records always report `identity` (not the fallback). JS `!v` ⟺ `v === undefined` here because `byId` values are always truthy verdict objects, matching Python `v is None`. Null-proto maps guard `__proto__`/`hasOwnProperty` keys on both sides. Membership of `unmatched` is identical (only the ordering caveat above).
- **Acceptance twins thread `unmatched` identically.** `acceptance_rereview.js:85` / `.py:107` both forward `normalOut.unmatched || []`. Acceptance (offered) verdicts are keyed to identities drawn from `merged`, so they always match a finding and never produce false unmatched; only the normal fold contributes. The `--acceptance-only` interactive mode (.py:133-141) filters to sameness verdicts and adds `unmatched` to output as a harmless superset field (interactive path does not ride the round-record loud channel — documented exception).
- **`unmatched` rides only when non-empty, consistently.** `review_panel_shell.js:1028` sets `verdictOut.unmatched` only when `length` > 0; `loop_readout.py:127-128` reads `record.get("unmatched") or []` and renders the section only when non-empty. This mirrors `downgrades` (verdictOut always / readout conditional), which already reaches the terminal record through the same `finalizeVerdict` → terminal-record pass, so `unmatched` follows a proven path. Empty case leaves the terminal record and readout byte-unchanged.
- **Bundle regenerated (SSOT §11).** `showrunner.bundle.js` carries the staged-id loop (:1791), the `matchedIds` bookkeeping + `unmatched` (:554, :573-574), acceptance `unmatched` (:1205), the loud log (:1806-1807), `verdictOut.unmatched` (:1943-1963), and both leaf verbatim instructions (code :6115-6117, doc :6228-6230). No source/bundle drift observed.
- **Fail-closed / keep-on-uncertain preserved.** An unmatched (mis-keyed) verdict still keeps every finding (never drops on a non-matching verdict); `unmatched` is visibility-only. Parity fixture 09 confirms a wrong verdict id keeps the finding and reports it unmatched.
