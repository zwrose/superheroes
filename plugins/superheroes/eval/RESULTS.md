# A/B Results — agent improvements vs faithful-port baseline

**Method:** offline dual-dispatch (see `README.md`). For each agent × fixture, a reviewer-simulating subagent ran twice — **baseline** (agent + rubric at `git show 5a05714:…`) and **improved** (working tree) — blind to the expected-findings manifest, then scored against `fixtures/<name>/expected.json` (scope-aware matching per README §Scoring).

**Date:** 2026-06-06. **Baseline ref:** `5a05714`. **Fixtures:** `web-handler`, `refactor`.

## Gate

**GREEN — improved ≥ baseline on recall AND precision for every agent, both fixtures.**
- **No lost findings:** improved caught every seed baseline caught (same seeds).
- **No FP inflation:** neither variant flagged any of the 6 planted traps.
- **One net-new true positive** from the improved side (web-handler Test, mutation-survival lens).
- **No regressions → no agent revision required.**

## Per-agent results

### web-handler fixture (one seed/dimension + 3 traps)

| Agent | Seed | Baseline | Improved | Traps flagged (B/I) |
|---|---|---|---|---|
| Architecture | premature-abstraction (`persistNote`) | caught (Minor) | caught (Minor, `abstraction-justification`) | 0 / 0 |
| Code | hardcoded-error-string | caught (Important) | caught (Important, `error-handling`) | 0 / 0 |
| Security | BOLA (`updateNote` id-alone) | caught (Critical) | caught (Critical, `BOLA` + evidence chain) | 0 / 0 |
| Test | claim-test-mismatch | caught (Important) | caught (Important) **+ 1 net-new** weak-assertion (mutation-survival) | 0 / 0 |

### refactor fixture (new-rule seeds + 3 traps)

| Agent | Seed | Baseline | Improved | Traps flagged (B/I) |
|---|---|---|---|---|
| Architecture | AcyclicDependencies (billing↔orders cycle) | caught (Important) | caught (Important, `Acyclic Dependencies`) | 0 / 0 |
| Code | cognitive-complexity (`classifyOrder`) | caught (Important) | caught (Minor, `cognitive-complexity` + Low null-deref extra) | 0 / 0 |
| Security | BFLA + BOPLA (`cancelAllOrders`, body-spread) | caught both (Critical/Important) | caught both (`BFLA`/`BOPLA` + evidence chain) | 0 / 0 |
| Test | mock-echo (`getOrderTotal` test) | caught (Important) | caught (Important) + risk-weighted coverage finding | 0 / 0 |

Traps correctly skipped by **both** variants in every case: pre-existing context-line BOLA smell, `./responses` sibling import, theme-token color (web-handler); size-only growth, clear-non-duplicative mapper, framework-escaped bound param (refactor).

## New rules: did they fire?

- **Acyclic Dependencies (arch):** fired on its seed (improved labels it). Note: baseline also caught the cycle — the fixture's CLAUDE.md states the acyclic convention, so baseline flagged it via module-coupling. Improved adds the named taxonomy.
- **cognitive-complexity (code):** fired on its seed. Baseline also caught it (the fixture profile's code focus hint nudges toward nested-branching), framed generically; improved names it and (correctly) risk-weights the pure-function case to Minor.
- **BFLA / BOPLA (security):** fired and labeled. These existed in the baseline under other names ("Privileged routes" Critical, "Mass-assignment" Important), so recall is equal; the improvement is the OWASP taxonomy label + the required **evidence chain** (entry → unguarded sink → reachable principal).
- **mutation-survival (test):** the clearest differential — improved flagged a weak `updates the title` assertion (a dropped-`$set` mutant survives) that **baseline did not** (web-handler). Net-new true positive.
- **size-needs-2nd-symptom (arch):** acted as a precision guardrail; the size-only trap was skipped by both (it sat under the raw-size threshold, so no asymmetry materialized — a sharper future fixture could exercise the >threshold-but-single-symptom case).
- **confidence + Chain-of-Verification:** every improved-variant finding carried `confidence`; the one genuinely uncertain finding (code null-deref on `order.items`) was correctly emitted at **Low** rather than dropped or over-asserted.

## Tokens

Improved output is modestly larger per finding (the `taxonomy`, `confidence`, and evidence-chain fields). Rough per-dispatch output tokens (improved / baseline): Architecture ~110/80, Code ~280/180, Security ~150/120, Test ~400/150. The increase buys structured, labeled, confidence-gated findings; it does not change recall or precision. Acceptable per the spec (record quality **and** tokens).

## Honest read

On these two fixtures the improvements are **non-regressing** (the spec's bar) and add: named taxonomies, a confidence gate, the security evidence-chain, and one extra real catch from the mutation-survival lens. They did **not** dramatically out-recall the baseline here, because both fixtures' profiles/CLAUDE.md already steered the baseline toward the seeded issues (focus hints for cognitive-complexity, the documented acyclic convention, pre-existing BFLA/BOPLA rules). That is a fair result, not a null one: the precision guardrails (size-2nd-symptom, threat-model-gated SSRF, diff-scoped secrets) are most valuable on *noisier* inputs than these tightly-seeded fixtures, and the taxonomy/confidence/evidence structure is a quality gain independent of recall. A future Plan-6 golden-eval can add a higher-noise fixture (a sprawling diff with many near-miss traps) to stress the precision guardrails directly, and the install-time live A/B against weekly-eats will measure the agents as registered `subagent_type`s rather than inlined methodology.

---

# Failure-Mode fixtures — single-variant runs (review-crew 0.3.0)

**Method:** premortem-only single-variant dispatch per `README.md` §Single-variant fixtures — one reviewer-simulating subagent per fixture, blind to `expected.json`, applying the working-tree `agents/premortem-reviewer.md` + `rubric/review-base.md`. Scored with `score.py` (no baseline; `gate: n/a`; mechanical bars instead).

**Date:** 2026-06-11. **Agent/rubric ref:** branch `feat/failure-mode-reviewer` (premortem agent as of commit d581e86, rubric-version 3).

| Fixture | Bar | Result | Outcome |
|---|---|---|---|
| `failure-modes` | `matched == total` | **5/5 matched** (all five classes), 0 traps | **PASS** (first run, no prompt iterations) |
| `failure-modes-bait` | `traps_flagged == 0` | **0 traps**, 0 findings emitted at all, 0 net_new | **PASS** (first run, no prompt iterations) |

**net_new on `failure-modes` (2, inspected):** both read as legitimate extra true positives, not FPs — (1) `partial-failure` on redeem.ts's mark-redeemed-then-credit sequence (two dependent writes outside a transaction — a real second partial-failure beyond the seeded race); (2) `detectability` on notify.ts returning `res.ok` so webhook failures pass silently. Caveat: both net_new entries cited line numbers that appear diff-relative rather than new-file-relative (out of range for their files). Note the five seed matches do not depend on exact line numbers — the whole-flow classes are function-scoped and score.py's taxonomy fallback (same file + same taxonomy) also matches — so a future re-run with sloppy line arithmetic should still pass this bar.

**Read:** the recall bar and the FP bar both pass on the first attempt. The bait fixture's three guards (profile-gated race, retryFetch wrapper, framework transaction) were each explicitly cited by the agent as reasons NOT to flag — the Do-NOT-Flag list and profile gate held under adversarial-looking input.

# Sharpened-agent A/B (review-crew 0.3.0)

**Method:** per `README.md` §Procedure, but **baseline ref = `0d6c5d9`** — the pre-sharpening merge-base of `main` (NOT the historical `5a05714`; the regression direction this run guards is sharpened-vs-current, and the historical baseline pre-dates the Plan-5 improvements). 2 agents × 2 fixtures × 2 variants = 8 dispatches, blind to `expected.json`; same runner conditions per variant pair.

**Date:** 2026-06-11. **Sharpening under test:** security-reviewer Critical attack-construction requirement; test-reviewer mutant-killing-test requirement (commit 679bed8).

Per-agent-dimension recall (own-dimension seeds) + traps:

| Agent | Fixture | Baseline | Improved | Traps (B/I) | Gate |
|---|---|---|---|---|---|
| security-reviewer | web-handler | 0/1 | 0/1 | 0 / 0 | **PASS** |
| security-reviewer | refactor | 1/2 | **2/2** | 0 / 0 | **PASS** |
| test-reviewer | web-handler | 0/1 | **1/1** | 0 / 0 | **PASS** |
| test-reviewer | refactor | 0/1 | **1/1** | 0 / 0 | **PASS** |

**Read:** improved ≥ baseline in every cell, strictly better in three. The FP-suppression worry (attack-construction pressure suppressing the web-handler BOLA Critical) did NOT materialize — improved flagged the BOLA at the same location as baseline. Zero traps flagged in all 8 dispatches.

**Caveat — absolute numbers are not comparable to the historical run above.** This run's subagents were sloppier at new-file line arithmetic than the original 2026-06-06 runner (e.g. both web-handler security variants cited the BOLA at line 26 vs the seed's resolved line 20 — same bug, same 6-line offset, outside the ±2 line-scoped window). Because both variants in each pair ran under identical conditions, the relative non-regression gate is valid; the depressed absolute matched counts are runner noise, not agent regressions.

# Manual plan-time scenario (M1)

**M1: PASS (methodology proxy).** Date: 2026-06-11.

The installed review-crew at run time was the cached 0.2.0 release (no `premortem-reviewer`), so the literal skill-tests.md §7 procedure — `/review-crew:review-plan` driving the 5-agent crew end-to-end — could not run in-session. Instead M1 was run as a **faithful methodology proxy**: a subagent applied the on-branch `agents/premortem-reviewer.md` + `rubric/review-base.md`, under the review-plan plan-time framing and the strict (no-profile) threat-model fallback, against `eval/samples/gappy-plan.md`, blind to the expected outcome. (The skill *wiring* that dispatches premortem-reviewer as the 5th plan-time agent is separately guarded by `lib/tests/test_dispatch_tables.py`; this proxy verifies the agent *behavior* M1 cares about.)

Both M1 acceptance criteria met, each citing the plan doc:

- **(a)** `assumption-violation` finding at `gappy-plan.md:18 ("Design")` — names the unstated single-writer invariant behind the dirty-flag dedup reasoning. ✓
- **(b)** missing **Failure-handling statement** at `gappy-plan.md:14 ("Design")` — `partial-failure` on the push-then-clear two-step write (crash between push and dirty-clear leaves dirty rows or duplicate index entries). ✓

Three additional correct gaps surfaced (all Important, all real for this plan): `concurrency/race` (concurrent scheduler runs double-push), `dependency-failure` (outbound HTTP push with no timeout/retry story), `detectability` (no log/metric for failure or dirty-row accumulation). No false positives.

A literal installed-plugin live-run remains available to anyone after `/plugin marketplace update` + `/plugin update` to 0.3.0 (re-run skill-tests.md §7); it is expected to reproduce (a) and (b).

# 0.10.0 release-eval — single-variant benchmark, all fixtures

**Method:** single-variant run of the release content (main `8a41387`; agents/rubric byte-identical to release PR #227 head `49f5429e5a5dd6abe79194088b0ef5bf4e523a28`), per `README.md` §Procedure adapted to one variant + §Single-variant fixtures. 10 Opus-pinned reviewer-simulating dispatches, blind to `expected.json`: 4 agents × {web-handler, refactor} + premortem-only × {failure-modes, failure-modes-bait}. Scored with `score.py` (`gate: n/a` — no baseline variant; release-qualification bars below). This is the **benchmark instrument** for the 0.10.0 `release-evidence` gate (RELEASING.md).

**Date:** 2026-07-05.

Own-dimension recall (strict `score.py`) + traps, per dispatch:

| Agent | Fixture | Own-dim recall | Traps flagged | Net-new (inspected) |
|---|---|---|---|---|
| architecture-reviewer | web-handler | **1/1** | 0 | 0 |
| code-reviewer | web-handler | **1/1** | 0 | 1 (cross-dim true positive: the ownership dual-filter miss, Security's seed) |
| security-reviewer | web-handler | 0/1 † | 0 | 1 († the BOLA itself) |
| test-reviewer | web-handler | 0/1 † | 0 | 3 († incl. the claim/test-mismatch itself; other 2 are real extra catches) |
| architecture-reviewer | refactor | **1/1** (AcyclicDependencies) | 0 | 0 |
| code-reviewer | refactor | 0/1 † | 0 | 3 († incl. classifyOrder cognitive-complexity; other 2 = cross-dim BFLA/BOPLA true positives) |
| security-reviewer | refactor | **2/2** (BFLA + BOPLA) | 0 | 0 |
| test-reviewer | refactor | **1/1** (mock-echo) | 0 | 1 (real coverage gap, not an FP) |
| premortem-reviewer | failure-modes | **7/7** (all seven classes) | 0 | 0 (9 findings emitted; the two extras — redeem.ts partial-failure, credits.ts race — were window-absorbed into their flows' seed matches, unlike 2026-06-11 where one listed as net_new on out-of-range lines) |
| premortem-reviewer | failure-modes-bait | n/a (0 findings emitted) | **0** | 0 |

**Mechanical bars (README §Single-variant fixtures): both PASS** — `failure-modes` matched == total (7/7, first run, now including the two newer `fail-direction` + `transport-contract` classes), `failure-modes-bait` traps_flagged == 0 (zero findings emitted at all).

**† Line-arithmetic caveat (3 cells, same class as the documented 2026-06-11 caveat):** in each strict-scored miss the dispatch DID emit the seeded bug — verified by hand against the seed's resolved location:
- security/web-handler: BOLA flagged at `notes.ts:26` vs seed resolved ~20 (the same 6-line offset both 2026-06-11 variants produced) — correct taxonomy `BOLA`, correct file, same `db.notes.update({ id }...)` call.
- test/web-handler: the `"returns 401 when not authenticated"` claim/test-mismatch flagged, cited `:74` (outside the ±2 window of the seed's resolved line).
- code/refactor: `classifyOrder` deep-nesting flagged (`cognitive-complexity spike`) — the seeded function (seed resolves to `orders.ts:12`, inside `classifyOrder`) — but cited `:89` (diff-relative arithmetic) and a non-exact taxonomy string, so neither the ±15 window nor the exact-taxonomy fallback fired.

Substantive own-dimension recall is therefore **8/8 cells** across the eight four-agent dispatches (the two premortem dispatches are covered by the mechanical bars above) — **16/16 seed instances** across all dispatches (web-handler 4 + refactor 5 + failure-modes 7, counting cross-dimension catches once, in their own dimension's cell). **Zero traps flagged in all 10 dispatches** — the precision guardrails (context-line, theme-token, sibling-import, size-only, framework-escaped, clear-non-duplicative, and all three bait reasons) held everywhere.

**Tokens:** ~50–58k total tokens per dispatch (subagent total incl. reading agent file + rubric + fixture; ~536k across all 10).

**Verdict: PASS** for the 0.10.0 benchmark instrument — no seeded regression anywhere the strict scorer OR hand-verification can see, zero false positives, both mechanical bars green on first attempt. The strict-scored misses are runner line-arithmetic noise (documented class), not agent regressions; absolute strict numbers remain non-comparable across runs per the 2026-06-11 caveat.
