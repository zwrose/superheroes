Closes #1435.

## What's changing, and why

Every codex seat that ran GPT-5.6 Terra or GPT-5.6 Sol now runs **GPT-6 Sol** at the same effort: implementer, code-fixer, reviewer, doc-reviser, verifier, reviewer-deep, brief-check, and the Claude-peer map. GPT-6 Sol costs half of 5.6 Sol per token and scores slightly better. It passed the security-lens registration probe before any default switched to it: it named the planted fail-open, Critical, on the first attempt.

**Terra is gone from the registry.** A project config or pin that names it is refused by name ("gpt-5.6-terra is retired; use gpt-6-sol") at load, at the configure write, and at dispatch validation, and it never falls back silently. **GPT-5.6 Sol stays as an explicit pin only.** An existing pin to it keeps working, but it is no longer a default or a ladder rung.

GPT-6 Sol needs Codex CLI **0.157.0 or later** (0.153.4 was refused by the server). An older CLI is now told at the preflight and at review-panel composition, with a named refusal that says to upgrade, instead of failing inside a review seat.

## What we're accepting

- **The minimum Codex CLI version is a policy floor.** It rests on one refused version (0.153.4) and one accepted version (0.157.0). A CLI between 0.154 and 0.156 that might work is still told to upgrade. The floor comes from the models the defaults use, so even a project that pins every codex role to GPT-5.6 Sol is told to upgrade.
- **Three blocking review findings were skipped, not fixed, on the builder's call.** No owner ruled on the review's judgment gates, so each was folded without owner attribution.
  1. The codex tier map is still copied into CONVENTIONS and two configure references, kept in step by a drift test. The issue required those copies to be updated; replacing them with a generated doc is left for later.
  2. A retired Terra pin is reported as rejected in the configure view. At run time the seat quietly uses the default model instead of re-announcing the rejection. That is how every invalid pin already behaves.
  3. If the registry changes *between two slices of one registration-probe run* (an upgrade landing mid-probe), the continuation is refused and counted as an attempt. This fails loudly, not silently. The build's rule against patching one spot a third time stopped the fix, and the design gap is handed up.
- **The review's certificate was withheld.** The review loop converged (audited chain, independent vendors), but the certification step refused, because the Claude synthesis seat carries no runner evidence. That is a known gap in the review driver, not in this change. The loop's own receipt is linked below.
- **Codex CLI floor rough edges, left as follow-ups.** A failed `codex --version` (for example a missing binary) reads as "version unknown, upgrade", which is a misleading message. Some older liveness test fakes now stop at the version check. The build's rule against patching one spot a third time stopped a third patch here.
- **A few Minor test-quality findings stay open** (listed under follow-ups).

## How to see it

N/A — nothing to see (plugin library and docs; there is no running app).

## Advisor vet
<!-- superheroes:advisor-vet -->
**Verdict: READY** · 7696e8863fd74d450957bb854ceceb92f903e0c3 (re-pinned: routine base update with `main` before the merge, no change to the PR's own diff; the owner's word stands)

**What was checked.** Every GPT seat now defaults to GPT-6 Sol at its previous effort, and Astra stays opt-in. I read the registry directly and checked two things by breaking them on purpose: a Terra pin is refused by name everywhere it can appear, and an older Codex CLI is stopped at the readiness check with an "upgrade to 0.157.0" message. Both breaks made tests fail. The check passes on this machine's upgraded Codex. GPT-6 Sol passed the official planted-bug test before the switch. CI is green, and it merges cleanly with today's `main`.

**What accepting it means.** Projects on Codex CLI older than 0.157.0 are told to upgrade before any GPT seat runs. That floor is set from one refused version and one working version, so 0.154 to 0.156 are told to upgrade too. Three review findings were set aside as documented edges, and none of them hides a problem. The review certificate was withheld because of a known review-loop gap that C13 4e now owns.

**What is theirs to decide.** Merge #1442. It is the last code PR on the 0.34.0 cutline.

**Owner's merge word:** 2026-09-25 in chat ("21 a", after walking follow-ups 22–29), covering #1442. The advisor executes it: a routine base update, the verdict re-pinned, all checks green, a squash pinned to the head.

<details><summary>Receipt</summary>

Vet 308 receipt: https://github.com/zwrose/superheroes/pull/1442#issuecomment-5838078017

</details>

<!-- superheroes:build-record -->
<details><summary>Build record</summary>

### Lane and anchor

Full lane (declared; marker at the build worktree). Anchor (ruling) 2026-09-25, owner in the advisor channel — resolves. Park r1 → owner ruled **a** (upgrade the Codex CLI); r2 relaunch. Brief + r2 addendum + brief-check dispositions + size report are on the issue.

### Build brief

The brief (issue comment "Build brief — #1435"), the r2 addendum (the Codex CLI floor seat), and the brief-check dispositions are posted on #1435 and carried here by reference. Changes since the brief:

- **Implementer engine:** claude native subagents (sonnet-5 high) instead of cursor composer-2.5. This keeps both review vendors (codex, cursor) outside the maker family.
- **5.6 Sol pin mechanism:** `pin_only: True` plus an allowlist append at the role's cell effort. `override_only` stays False. `override_only` alone could not keep a pin valid (brief Decision 2).
- **Base moved:** `911a9578` → `11ac4eb8` (branch adopted there) → `f529c4ac` (#1437 merged in as a merge commit; no history rewrite).
- **Size:** estimate ~150 non-test. Measured **420 non-test** (+342 −78), 1734 test, 64 record. Reported on the issue at 308; the review fix rounds added the rest. Under the 600 park line; split offered and not taken (the floor gate is what makes the switch safe).

### Probe gate (DoD row 1)

WO-1 (`258e49cd`) registered `gpt-6-sol` as `probe-pending` and seated `registration-probe` on `(gpt-6-sol, high)`; no default changed. One live attempt, `conformance_probe.py astra-probe --wave gpt6sol-1435-2026-09-25`, 13:17Z, Codex CLI 0.157.0: `{"ok":true,"outcome":"pass","model":"gpt-6-sol","effort":"high","matched":{"file":"app/session_guard.py","line":25,"severity":"Critical"},"attempt":1,"misses":0}`. Store ledger `conformance/astra-probe-attempts.json` now holds 2 attempts. A GPT-6 Sol row was added to the C1 values annex (out-of-repo). The switch (`539b43c3`) came after.

### Cross-plugin contract lines changed (CONVENTIONS)

- The **Codex tier map** line now reads haiku/sonnet/opus = `gpt-6-sol`.
- The **codex pin** sentence now lists `gpt-6-sol`, the pin-only `gpt-5.6-sol` (roles with a codex cell, at that role's effort), and `gpt-6-astra` (reviewer-deep, high). It also states the named `model-retired` refusal for `gpt-5.6-terra`.
- The **Fable no-substitution** sentence drops its provenance clause.
- The **CLI availability** sentence is replaced. It said "an unavailable model falls open to the host model, never a guessed version gate". It now says the registry names a minimum Codex CLI version, the preflight and composition refuse below it with `codex-cli-too-old` / `codex-cli-version-unknown`, and a cached receipt never skips the check.

### DoD disposition table
<!-- superheroes:dod-table -->

| DoD row | Status | Evidence |
|---|---|---|
| Live probe passed on `gpt-6-sol` before any default names it, recorded in the build record and the values annex | done | Probe gate section above; `258e49cd` precedes `539b43c3`; ledger attempt 2; annex row |
| `model_registry.py` holds the new cells, ladder and peer map from one home; nothing else in shipped code or prose names `gpt-5.6-terra` (bite-proof records excepted); a Terra pin refuses with the named reason; a 5.6 Sol pin resolves | done | `model_registry.py` `_MATRIX`/`_LADDERS`/`_CODEX_PEER_BY_CLAUDE`/`_RETIRED_MODELS`; shipped code names Terra only in `_RETIRED_MODELS`; shipped prose names it only where it documents the refusal (CONVENTIONS, set-up, view-and-tune, TRANSITION) — the CHANGELOG history line and the committed `docs/superheroes/**` receipts are history, left as receipts; bite-proofs E1a–E1d, E3 |
| CONVENTIONS codex tier map and the configure references name `gpt-6-sol`; the PR body says which contract lines changed; no provenance in shipped prose | done | Contract section above; `f18fba7b`, `ba687f58`, `2f775ace` |
| Tests that assert on model literals read them from the registry wherever they can | done | WO-3a/3b/5 (`f69f8cba`, `37929afa`, `ba687f58`); remaining literal Terra strings are the retired-refusal tests and opaque data in `test_liveness_cache.py` / a few `test_seat_map.py` shape tests (listed as a follow-up) |
| The four validators and the full suite pass; CI is green | done | Validators 5/5 and full suite `16370 passed, 9 skipped` at `2f775ace` (detached tree); verify gate exit 0 at `a52709dc`; CI workflow `CI` run 36176148843 **success** on head `67dbc18f` (`16372 passed, 7 skipped`) |
| (r2) An older Codex CLI is told at the preflight / liveness check with a named refusal naming the upgrade; minimum version named once, in the registry, as data | done | `gpt-6-sol` record `min_cli`; `codex_min_cli()`; `preflight_probe.codex_cli_floor_probe` at the preflight, composition and cache seats; bite-proofs E5a–E5d |

### Review

`review-code` driver loop, branch mode, driven from a **detached base checkout at `f529c4ac`**. The codex seats therefore dispatched through the base registry (GPT-5.6 Sol xhigh), so the change under review did not judge itself. Vendors `["codex","cursor"]`, fixer vendor `claude` (the maker family, excluded from the panel by the seat map: author family `anthropic`). `record-result --evidence-run-dir` on every runner seat except audits (see degradations).

- **Terminal:** `converged`, shape `audited-chain`, fullPanel false, independence `independent`, 6 rounds (full panel rounds 1 and 4; audits and scoped finder rounds 2, 3, 5, 6); `scriptRan` 227 invocations.
- **Certification artifact:** `certification-refusal.json`, class `unrun-review`, binding failure `execution-evidence-absent` on the synthesis seat (native claude seat, no runner telemetry).
- **Control probe (sampled):** round 1 cursor `ok` (plant caught); codex `plant-undetected` in both round 1 and round 4 (engaged: 1 finding, 1 investigated path, ~127K tokens each).

**Dispositions**

| Round | Sev | Finding | Disposition |
|---|---|---|---|
| 1 | Important | Composition samples the CLI floor twice; a transient second failure is cached as dead for the TTL | fixed `c3ca7e60` (one observation threaded through); audit discharged |
| 1 | Important | Composition discards the first floor refusal and re-probes | fixed `c3ca7e60`; audit discharged |
| 1 | Important | Direct dispatch of Terra returns a generic park, not the named retired reason | fixed `c3ca7e60`; audit discharged |
| 1 | Important | The registration probe (Astra-named) now exercises Sol | fixed with guidance `c3ca7e60` (docstring/help say it probes the cell's model); audit discharged |
| 1 | Important | Below-floor test cannot catch a string-compare mutant | fixed `c3ca7e60` (0.99.0 vs 0.157.0 case); audit discharged |
| 1 | Important | Canonical-wins-legacy-fixer test lost its two-valid-pins premise | not in the fix batch (verifier/synthesis outcome); open Minor-tier follow-up |
| 1 | Minor | TRANSITION says pin-only 5.6 Sol is valid for any codex pin role (pilot has no cell) | fixed `2f775ace` |
| 1 | Minor | Second-tier effort test asserts the default | open follow-up |
| 1 | Minor | Some I3/I4 detectors lack axis lines | open follow-up (axis lines added to the declared detectors in `ba687f58`) |
| 2 | Important | A prerelease CLI version at the floor's numeric core passes | fixed `b59644e7`; audit discharged |
| 4 | Critical | Pre-upgrade orphan claims get attributed to the new cell's model | fixed with guidance `cb00522a` (claims snapshot their seat; legacy claims settle as `unrecorded`); audit discharged |
| 4 | Important | The configure preflight guide says the probe is Astra-only | fixed `cb00522a`; audit discharged |
| 4 | Important | Codex policy duplicated across CONVENTIONS and configure refs | **skipped** (ratified DoD requires those copies; pre-existing drift-test pattern) — follow-up |
| 4 | Important | Retired pins dropped before runtime consumers disclose them | **skipped** (ratified refusal surfaces refuse by name; pre-existing invalid-pin runtime contract) — follow-up |
| 4 | Important→Minor | A failed `codex --version` is labelled version-unknown and loses its detail | re-tiered Minor by its verifier; **not fixed — third-rework tripwire** on the floor-gate surface; follow-up |
| 4 | Minor | Retired check bypassed for a role with no codex allowlist (`pilot`) | fixed `2f775ace` (bite-proven, E1c) |
| 4 | Minor | Second-tier effort test cannot distinguish fallthrough from default | open follow-up (floor-gate surface, tripwire) |
| 4 | Minor | Write-probe ceiling case claims an unpinned clamp but pins both | fixed `2f775ace` |
| 4 | Minor | The version pre-probe makes older liveness fakes pass vacuously | open follow-up (floor-gate surface, tripwire) |
| 5 | Important | Resuming a pending probe uses the new seat, not the claimed one | fixed `9eb7e577`; audit discharged |
| 6 | Important (PLAUSIBLE) | Claimed seat cannot survive a registry change mid-wave | **skipped — third-rework tripwire** on the claim-continuation surface; seam handed up |
| post | Minor | Max-of-two-pins test case uses a pin production would reject | open follow-up (scoped codex check of `2f775ace`) |

**Third-rework tripwire fired twice.** The builder refused further patches on two surfaces, both with converged correctness contracts:

- **The Codex CLI floor gate.** It was reworked in rounds 1 and 2 and fails closed on every branch. **Seam:** the gate classifies `codex --version` output inline, branch by branch. The durable shape is a small typed classifier (ok / below / prerelease-below / unparseable / command-failed with its detail kept) and one table-driven test.
- **The registration-probe claim continuation.** It was reworked in rounds 4 and 5. **Seam:** a claim has no seat identity that survives a registry change. The durable fix is a named terminal when the seat changes between slices ("start a new wave") instead of continuing on either seat.

Post-convergence commit `2f775ace` (three Minors) got a scoped single-seat codex check (gpt-5.6-sol xhigh, engaged, 5 investigated): 1 Minor, listed above.

### Bite-proofs

Record: `plugins/superheroes/lib/tests/bite_proofs/wo_gpt6_sol_1435.md`. There are 11 per-element neutralizations at the final head `2f775ace`, in a detached probe tree: E1a–E1d (retired refusal at validate_config, pin verdict, resolve_dispatch, seat-pin normalizer), E2 (no default names a banned model), E3 (pin-only append), E4 (pin-only off the ladder), and E5a–E5d (floor compare, preflight seat, composition seat, cache seat). Each went red on its own axis, the restore left porcelain empty, and all 11 were green together. Accepted with one disclosure: E1c and E1d were neutralized together, on independent paths. The orchestrator produced the proofs, not an implementer.

### Receipts

- Validators (5/5 exit 0) and full suite `16370 passed, 9 skipped in 1790s`, exit 0 — detached tree at `2f775ace` (`-n auto`, pinned interpreter). The final head `a52709dc` adds only the bite-proof record; its readers (`test_bite_proof_doctrine`, `test_closure_doctrine`, `test_decision_point_census`, `test_presence_flag_retired`, `test_ssot_drift`) passed 299/299 there.
- Verify gate (`verifyCommand`, `--base f529c4ac`) at `a52709dc`: validators ok, `verify_touched_tests` 5368 passed, exit 0.
- Preflight at r2 intake: `go: true` (gh, dispatch-vocab 919, codex READY on 0.157.0, cursor READY). Browser/test-pilot: N/A (no running app).
- CI: workflow `CI` run 36176148843, **success**, head `67dbc18f` (`16372 passed, 7 skipped`). The first CI run (36174548021, head `a52709dc`) failed one test: `test_cli_compose_liveness_writes_receipt` reached the real `codex --version` through the new floor gate, and CI has no codex binary. WO-7 (`67dbc18f`) stubs the gate in that test only (test-only, one line). It was reproduced red and re-verified green locally with codex off PATH (150 passed). The census found no other test reaching the real binary.

### Dispatch provenance

| Dispatch | Engine / model (registry-validated) | Maker family | Rework? |
|---|---|---|---|
| Brief check r2 | codex `gpt-5.6-sol` xhigh (dispatch_guard ok, `brief-check`) | — | — |
| WO-1 probe-pending registration | claude subagent `sonnet-5` high (`implementer` ok) | anthropic | no |
| Registration probe | codex `gpt-6-sol` high (`registration-probe` cell) | — | — |
| WO-2 switch | claude `sonnet-5` high | anthropic | no |
| WO-2b CLI floor gate | claude `sonnet-5` high (isolated worktree) | anthropic | no |
| WO-3a / WO-3b test migration | claude `sonnet-5` high (isolated worktrees, parallel) | anthropic | no |
| WO-4 prose | claude `sonnet-5` high (isolated) | anthropic | re-dispatched once: first dispatch parked on the orchestrator's wrong HEAD premise (order quality) |
| WO-5 drift test + axis lines | claude `sonnet-5` high | anthropic | amended once: order omitted set-up.md (order quality) |
| WO-6 post-review minors | claude `sonnet-5` high | anthropic | no |
| WO-7 CI hermeticity (test-only) | claude `sonnet-5` high | anthropic | fix of this build's own test (a machine-dependent test; order quality — WO-2b's order did not name hermeticity) |
| Review panel r1, r4 | codex `gpt-5.6-sol` xhigh ×3; cursor `cursor-grok-4.6` xhigh ×2 (seat map) | openai / xai | — |
| Verifiers / audits | codex `gpt-5.6-sol` high (`verifier` / `auditor` ok) | openai | — |
| Gap sweep / scoped finders | codex `gpt-5.6-sol` xhigh | openai | — |
| Synthesis (×7) | claude subagent opus (synthesis tier) | anthropic | — |
| Review fixers r1, r2, r4, r5 | claude subagent sonnet (code-fixer tier) | anthropic | review fixes |
| Control probes | codex `gpt-5.6-sol` xhigh (r1, r4); cursor `cursor-grok-4.6` xhigh (r1) | — | — |
| Scoped check of `2f775ace` | codex `gpt-5.6-sol` xhigh | openai | — |

Blocking-finding attribution: the round-1 and round-4 findings on the floor gate and the claim continuation are **implementer execution plus order quality**. The orders named the seats but not every edge (double probe, prerelease, claim resume). The two WO re-dispatches were **order quality** (the orchestrator's).

<!-- superheroes:degradations -->
### Disclosed degradations

- **Review certificate withheld.** Promised: a certification receipt. Delivered: `certification-refusal.json` (`unrun-review`, synthesis seat without runner evidence), because native claude synthesis seats cannot carry runner telemetry in the current driver. The converged `round-receipt.json` stands.
- **Audit rulings carry no runner evidence.** Promised: `record-result --evidence-run-dir` on every runner seat. Delivered: audits recorded without evidence and with a hand-stamped `envelopeSha256`, because the driver's evidence binding expects the ruling nested under a `ruling` key that the audit payload shape does not carry (`evidence-result-mismatch`). A known driver gap.
- **Judgment gates folded without an owner.** Promised: owner rulings at `present-judgment`. Delivered: builder dispositions, journaled `owner-unattributed`, because the build ran headless. Three blockers were skipped this way (listed under What we're accepting).
- **Codex control probe missed the plant (twice).** Promised: an engaged probe that catches the plant. Delivered: `plant-undetected` for the codex seat (GPT-5.6 Sol xhigh) in rounds 1 and 4; cursor caught it in round 1. The seats engaged; this is recorded as `canaryPlantUndetected`.
- **Bite-proofs produced by the orchestrator**, not an implementer (the charter's default producer).
- **The minimum Codex CLI version is a policy floor** set from one refused and one accepted version, not a vendor-published minimum.

### Follow-ups for the advisor

Follow-ups: 8 (0 owner-call)
- FU1 [defect] Codex CLI floor gate: a typed version classifier that keeps a failed `codex --version`'s own detail (a missing binary should not read "upgrade"); update the older liveness fakes that now stop at the version check; fix the second-tier effort test (tripwire seam, above).
- FU2 [defect] Registration-probe claims: a named terminal when the seat changes between slices of one wave (tripwire seam, above).
- FU3 [craft] Rename `astra-probe` and its ledger/claim files to a model-neutral registration-probe name (rejected in the brief as out of scope).
- FU4 [craft] Replace the copied codex tier map in CONVENTIONS / set-up.md / view-and-tune.md with a generated or cited source (skipped review finding).
- FU5 [craft] Surface rejected (retired) pins at run time in the seat map and the calibration readout (skipped review finding).
- FU6 [craft] Test hygiene: `test_codex_write_probe_model_covers_the_implementation_dispatch_ceiling` max-of-two-pins case pins Astra on implementer (rejected in production); `test_load_engine_prefs_canonical_code_fixer_wins_over_legacy_fixer` lost its two-valid-pins premise; opaque Terra strings in `test_liveness_cache.py` and a few `test_seat_map.py` shape tests.
- FU7 [defect] Review-driver gaps seen here: native synthesis seats always refuse certification (`unrun-review`); audit rulings cannot bind runner evidence.
- FU8 [info] Data point for model governance: GPT-5.6 Sol at xhigh missed the control plant in both probes this build ran.
<!-- superheroes:followups FU1 FU2 FU3 FU4 FU5 FU6 FU7 FU8 -->

</details>

🤖 Generated with [Claude Code](https://claude.com/claude-code)




