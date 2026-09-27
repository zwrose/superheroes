Closes #1238.

## What's changing, and why

A project can now list the checks the advisor's vet must run, as a `vetChecks` list inside `core.md`'s existing machine-readable JSON block. Each check names the check, where the vet reads its evidence, and what the vet records. This is the home for rules whose proof lives in the PR body or a ledger, which review seats cannot read.

This is the owner's 9 = a rework. The earlier version kept the checks in a hand-parsed markdown section, and ten review rounds were spent on where that section starts and ends. A key in the block the tools already parse removes that problem by construction. The earlier version stood at 693 lines; this one is 460.

What ships:
- one validator;
- a read command that never reports a broken or malformed list as "no checks";
- a writer, with clearing as an explicit `--clear`;
- the list on `configure`'s one-screen view;
- the vet-receipt doctrine that tells the advisor how to act on it.

No project's actual checks ship here; those encodings belong to P5 and the weekly-eats DE work.

Round 3 (after vet 304) brings the branch up to date with `main` and fixes three command lines that still used the old way of locating the plugin. It also closes the checker gap that let them through: the skill validator now refuses that old form anywhere in shipped docs, not only when a file path follows it.

## What we're accepting

- **An older plugin build can silently drop the list.** If an older installed build (0.33.0 or earlier) confirms a project's calibration after checks were declared, it drops the `vetChecks` list. The schema version stays at 2, the same accepted residual `projectConfiguration` already carries. The fix is the pending schema bump tied to a release.
- **The review panel was a single vendor family.** Every seat ran on codex `gpt-5.6-sol` at xhigh, as ordered. The maker (cursor) was excluded, and the default seat map's two claude seats were pinned to codex. There was no second family to cross-check codex.
- **The planted-defect control probe missed its plant.** The round-1 probe on codex was engaged but did not flag the planted defect (`plant-undetected`). That withholds the panel-level certification signal for this round. The probe ran once, as a sample.
- **The review loop has no signed certification record.** The driver's verdict is `converged` (3 rounds, `audited-chain-degraded`), but the certification writer refused to record it (`unrun-review`). The synthesis step ran as a native Claude subagent: the model registry seats synthesis only on Claude, and the runner has no synthesis path, so that seat carries no execution evidence.
- **One review decision was made by the driver's default, not by you.** A tradeoff finding (empty input silently clearing every check) hit the owner-judgment gate while you were away. It took the default "fix as suggested" and is recorded as owner-unattributed. The fix: empty input is refused, and clearing needs `--clear`. The configure recipe says so.
- **Round 3 had one reviewer, not the full panel.** The advisor's order named one cross-vendor seat for the round-3 changes. Codex returned nothing usable on the docs change, so cursor `grok-4.6` read it all and found nothing. The new validator check was written by a Claude implementer, so that reviewer is independent of it.
- **I typed the three-line docs fix myself.** In the full lane, implementation is normally handed to an implementer. The advisor's order gave the exact replacement text, so I applied it directly; the cursor reviewer checked it.
- **Two Minor review findings are not fixed** (listed under follow-ups):
  - the CLI reports JSON `null` input as "unparseable" rather than malformed;
  - one validator-ordering test checks a single unordered field.

## How to see it

N/A. Routed "nothing to see": this is plugin library and doctrine code with no running app, and no project declares checks yet.

## Advisor vet
<!-- superheroes:advisor-vet -->
**Verdict: READY** · ce9228178eed6eaf2e548dba38367ab6f9e6de9a

**What was checked.** An independent read found one problem, and it is now fixed: the PR had brought back an old plugin-root form that C15 retired, and no check caught it. The PR now uses the current form, and the validator catches the old form everywhere; putting one line back turns it red. On the feature itself:
- a project's list of vet checks survives an unrelated calibration write;
- duplicate or malformed entries are refused;
- a broken or unreadable list never reads as "no checks".

Each of the first two was checked by breaking it on purpose and watching the tests fail. The PR merges cleanly with today's `main`, where its tests and the four validators pass.

**What accepting it means.** Projects can now declare checks the advisor's vet must run; none is declared yet. The review behind this PR was weaker than usual: one reviewer family, a missed control plant, and no signed certification (all disclosed in the PR). The advisor's own probes on the key guards stand in for that. An older installed plugin (0.33.0 or earlier) can still drop a declared list if it confirms calibration; that clears with the release's schema bump.

**What is theirs to decide.** Merge #1437 (on the 0.34.0 cutline).

<details><summary>Receipt</summary>

Vet 304 receipt, with the delta re-check: https://github.com/zwrose/superheroes/pull/1437#issuecomment-5833686021

</details>

<!-- superheroes:build-record -->
<details><summary>Build record</summary>

### Lane and base

- **Lane:** full, declared via `build_lane.py declare` (`ok: true`).
- **Base:** `main` `5de88598` through r2. In r3, `main` `11ac4eb8` was merged in (merge `5bf50390`, no conflicts; no rebase, no force-push).
- **Branch:** `build/1238-vet-checks-json-key`. Final head `ce922817` (r3). The r2 head was `c6ae639f`: the last code head `5ced489f` plus the bite-proof record.
- **Reference branch:** `build/1238-vet-checks-section` (`04d295e4`) was used for reference only and never opened as a PR.
- **Size:**
  - **non-test 460** (+437 −23): core_md +304/−20, configure_view +46/−1, docs +87/−2;
  - test 749;
  - record 51.
- **Against the order's lines:** over REPORT 300 (reported on the issue at 408), under PARK 600. It sits exactly at the brief's 2× line (2 × the revised 230 estimate). The final 52 lines came from the review loop's fixes.
- **After r3** (measured against `origin/main...HEAD`): **non-test 490** (+462 −28), test 792, record 51. The r3 delta: `validate_skills.py` +25/−5, the two reference docs +3/−3, test +43. Still under PARK 600.

### Build brief

Posted on the issue: [brief](https://github.com/zwrose/superheroes/issues/1238#issuecomment-5831606267), [pre-code check dispositions and change log](https://github.com/zwrose/superheroes/issues/1238#issuecomment-5831676830), [size report](https://github.com/zwrose/superheroes/issues/1238#issuecomment-5831935928).

**Shape.** The optional key `vetChecks` is a JSON list of `{name, evidence, records}`: non-empty strings, unique names. One validator, `validate_vet_checks`, backed by the closed token set `VET_CHECKS_MALFORMED_REASONS`, is the only judge of its shape.

**Reading** (`read_vet_checks` / CLI `vet-checks`) fails closed. Each of these gets its own reason, never "none declared":
- `repo-root-unavailable`
- `core-md-absent`
- `core-md-unreadable`
- `core-md-unparseable`
- `multiple-core-blocks`
- `duplicate-core-key:<k>`
- `vet-checks-malformed`

**Writing.** `write_vet_checks` / CLI `write-vet-checks` validates before touching disk and reuses the shared single-key block writer. `[]` stays as declared-empty. Empty stdin is refused. `--clear` removes the key.

**Preservation.** `parse_core`, `read`, `render_core` and `confirm` carry the key by membership, never by truthiness, so every other core.md writer preserves it, malformed values included.

**Seams.**
- `confirm()` used to drop unknown block keys; it now carries this one.
- Validation lives outside `parse_core` on purpose. A malformed vet-only key must not make every hero's dispatch gate read the core as corrupt.
- The other writers' round-trip guards now cover the key by construction.

**Rejected alternatives:**
- validating inside `parse_core`;
- a dict keyed by name;
- per-check item writes;
- a schema bump (release-coupled, outside the ratified scope).

**Consequential flags:** none. No migration, dependency, gate or hook.

**Pre-code check.** Codex `gpt-5.6-sol` xhigh, engaged. 8 Important findings: 7 folded, 1 disputed (the schema bump; disclosed above).

<!-- superheroes:dod-table -->
### DoD disposition

| DoD bullet | Disposition | Evidence |
|---|---|---|
| The shape ships (per check: name, evidence source, what the vet records); consumed by calibration per plugin conventions | done | `core_md.py` `VET_CHECKS_KEY`, `validate_vet_checks`, `read_vet_checks`, `write_vet_checks`, `clear_vet_checks`, CLI `vet-checks` / `write-vet-checks`; `configure_view.py` Vet checks block; tests `test_core_md_vet_checks.py`, `test_configure_view_vet_checks.py` |
| Rework scope: validated where the core block is validated, ONE validation home, malformed refuses with a named token | done | `validate_vet_checks` + `VET_CHECKS_MALFORMED_REASONS` (six literal-pinned tokens); bite-proofs E1–E6, E10 |
| Rework scope: read through the core read path; absent = none; malformed refuses, never "none" | done | `read_vet_checks` legs; bite-proofs E7, E9, E11; tests `test_read_vet_checks_*` |
| Rework scope: write through the core write/confirm path; an unrelated core write preserves the key | done | `test_preservation_matrix` (10 writers × valid / malformed / empty seeds); bite-proofs E8, E13 |
| Configure shows the checks; vet-receipt names the home and the triggered field | done | `configure_view._vet_checks_view_lines`; `vet-receipt.md` § Project vet checks + triggered-fields row; `view-and-tune.md` recipe; `CONVENTIONS.md` core.md bullet; `LEDGERS.md` row |
| The two repos' first encodings are NOT this issue's (P5 and weekly-eats DE own them), stated as scope boundary | done | `vet-receipt.md`: "This section defines the shape only. Encoding checks is the project's work, done through `configure`." |
| Validators green; citation-resolution green | done | the four validators green on `5ced489f` and again on the r3 head `ce922817` (`validate_skills.py` carries the §11.4 citation resolution): see Receipts |

### Receipts (all re-run by me)

- **Validators on the final code head `5ced489f`**, in a detached probe tree:
  - `validate_marketplace` ✓
  - `validate_hosts` ✓
  - `validate_skills` ✓ (token shape + §11.4 citations)
  - `validate_stubs` ✓
- **Full suite** (the CLAUDE.md command, `-n auto`) on `5ced489f`, detached probe tree: `16220 passed, 9 skipped` (exit 0, 1173 s).
- **Verify gate.** `verify_gate.py --command "<session verify command, --base 5de885983577>"` on `5ced489f` → `result: pass`.
- **Session verify command before each fixer landing:**
  - round-1 fixer `c3092531`: rc 0, `2819 passed`;
  - round-2 fixer `5ced489f`: rc 0, `2820 passed`.
  - The driver's `run-verify` phase folded `pass` from those same runs. Each was on the identical head and command, with a clean tree.
- **Remote head:** `origin/build/1238-vet-checks-json-key` = local `c6ae639f` at r2; `ce922817` at r3. Checked after every integrated commit.
- **CI:** workflow `CI` run [36142134935](https://github.com/zwrose/superheroes/actions/runs/36142134935) on head `c6ae639f21081192632bf78ba471391b0bc838d0`: `validate` **success** (10m9s); `pr-title` pass.
- **CI (r3):** workflow `CI` run [36144904027](https://github.com/zwrose/superheroes/actions/runs/36144904027) on `8949f100f6f0cae05a3569127e39db3d08d385ca`: **success**. Final head: workflow `CI` run [36146217274](https://github.com/zwrose/superheroes/actions/runs/36146217274) on `ce9228178eed6eaf2e548dba38367ab6f9e6de9a`: `validate` **success** (9m29s); `pr-title` pass.
- **Change after the last review:** `c6ae639f` only adds the bite-proof record (a receipt file). Per the post-review delta table that needs receipts only; the record is excluded from the suite's censuses.

### r3: base update + retired-form fix

The r3 order (issue #1238 top STATE block, from vet 304; step 3 added at the owner's sitting, item 16). Intake: [comment 5833701083](https://github.com/zwrose/superheroes/issues/1238#issuecomment-5833701083). No unpushed residue in any 1238 worktree.

- **Step 1:** `git merge --no-ff origin/main` at `11ac4eb8` → merge `5bf50390`, clean.
- **Step 2:** `8949f100`, three `ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"` lines → `ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"` (`vet-receipt.md` ×1, `view-and-tune.md` ×2). After it, `git grep -n 'CLAUDE_PLUGIN_ROOT:-' -- plugins/superheroes ':!*/tests/*'` returns nothing (exit 1). Orchestrator-typed (see degradations).
- **Step 3:** `ce922817`, WO-r3. `_RETIRED_REF`'s `/path` is now optional, and every consumer formats through one `_retired_label` helper, so the bare form reports `retired plugin-root form (bare)`. Path-form messages are byte-identical. A bare form does not trip the one-hop `reference-depth` gate. A new `check_retired` leg runs over the §11.4 scan set (agents/, rubric/, reference/ trees) as `citation: <doc>: retired plugin-root form <label>`. Four new tests.
- **Receipts, re-run by me** in detached probe trees (`8949f100`, then `ce922817`):
  - four validators exit 0 on both heads;
  - targeted suites under `-n auto` (`test_validate_skills`, `test_core_md*`, `test_configure_view*`, including the vet-checks files): `489 passed` on `ce922817` (`422 passed` on `8949f100` without `test_validate_skills`).
- **Bite-proof (real tree, `ce922817`).** I put the bare line back in `skills/showrunner/reference/vet-receipt.md` with an Edit.
  - **RED** (rc 1): `reference-link: superheroes/showrunner: retired plugin-root form (bare) (in skills/showrunner/reference/vet-receipt.md)` and `citation: plugins/superheroes/skills/showrunner/reference/vet-receipt.md: retired plugin-root form (bare)`.
  - **Contrast:** the pre-r3 validator (`8949f100`'s `validate_skills.py`) on the same mutated tree: rc 0, `✓ skills meet token-shape rules`. That is the gap step 3 closes.
  - **Reverted** with the inverse Edit → **GREEN**: rc 0, `✓ skills meet token-shape rules`.
- **Bite-proof (unit level, re-run by me).** Made `/path` required again in `_RETIRED_REF` → **RED**: 4 failed, 63 passed. The four new tests fail, e.g. `assert [] == ['reference-l... form (bare)']`. Reverted → **GREEN**: 67 passed. The implementer's own red→green on `test_links_flag_retired_plugin_root_form_bare` matched.
- **Review (one cross-vendor seat, as ordered).** `dispatch-review --diff-base 5bf50390`, so it reads r3's own commits and not main's content. The prompt also ordered the merge-interaction check on the four files both sides touched: `CONVENTIONS.md`, `LEDGERS.md`, `view-and-tune.md` and `vet-receipt.md`.
  - codex `gpt-5.6-sol` xhigh: terminal `vacuous` (engaged, 14 tool calls). This is the order's named fallback case.
  - cursor `cursor-grok-4.6` xhigh: terminal ok, engaged (59 tool calls, 299 s), **0 findings**. Its `investigated` list: `validate_skills.py`, the test file, conftest, `ci.yml`, both reference docs, `CONVENTIONS.md`, `LEDGERS.md`, `core_md.py`, `configure_view.py`, `scripts/pinned-python`.
- **CI:** see Receipts. **Remote head:** `origin/build/1238-vet-checks-json-key` = local `ce922817`.

### Review (`review-code`, driver session)

Durable receipt: [PR comment 5833490843](https://github.com/zwrose/superheroes/pull/1437#issuecomment-5833490843).

- **Driver:** `round_driver.py` from the detached `5de88598` checkout. Session `/tmp/review-ATIdQqBG` (id `759745b2…`), durable-record path, `record-result --evidence-run-dir` on every runner seat.
- **Driver flags:** `--vendors ["codex","cursor"]`, `--fixer-vendor cursor`. Author family `xai`.
- **Seat map:** all five lenses pinned to codex `gpt-5.6-sol` xhigh. `critical-diversity` relaxed, host model unknown; both disclosed.
- **Verdict:** `converged` in 3 rounds (round 1 full panel; rounds 2–3 delta audits + scoped finder).
  - Certification shape: `audited-chain-degraded` (driver: `seat-pin`), `fullPanel: false`, independence `independent`.
  - `scriptRan` 97 invocations.
  - The certification writer refused `unrun-review` (`artifact: synthesis`, `execution-evidence-absent`): see *What we're accepting*.
- **Control probe (round 1, codex):** engaged, `plant-undetected`.
- **Judgment gate (round 1):** one finding, folded `fix-as-suggested` via `advance --owner-artifact` without `_provenance`, so it is recorded as owner-unattributed.

**Review dispositions**

| # | Finding (severity as raised) | Disposition |
|---|---|---|
| 1 | Architecture: vet-check schema has multiple authoritative homes (Important) | fixed r1: field names + tokens single-sourced in `core_md`; the validator emits the registry constants. Audit r2: discharged |
| 2 | Code: advertised malformed-reason registry does not drive validation (Important) | fixed r1, grouped with #1. Audit r2: discharged |
| 3 | Architecture: writer collapses declared-empty into absent (Important) | fixed r1: `[]` persists; `--clear` removes. Audit r2: discharged |
| 4 | Test: test blesses `[]` as deletion (Important) | fixed r1, grouped with #3 |
| 5 | Failure-Mode: empty stdin silently deletes all vet checks (Critical, tradeoff → owner gate; carried Important after verification) | fixed r1 as suggested (gate default, owner-unattributed): empty stdin refused `vet-checks-input-unparseable`, explicit `--clear`. Audit r2: discharged-but-new-issue (stale configure recipe), fixed r2, audit r3: discharged |
| 6 | Test: no-core test misses the false "unreadable" warning (Important) | fixed r1: absent core renders "none declared". Audit r2: discharged |
| 7 | Code: configure view misstates absence and drops malformed-field details (Minor) | fixed r1, grouped with #6 |
| 8 | Test: new suites omit their in-code `# axis:` disclosures (Important) | fixed r1 partially; audit r2: not-discharged; fixed r2 (40/40 tests carry axis lines); audit r3: discharged |
| 9 | Code (scoped finder r2): multi-line field values corrupt the configure screen (Important) | fixed r2 via `_one_line_prose`. Audit r3: discharged |
| 10 | Coherence (audit r2): documented clear command now always refuses (Important) | fixed r2: `view-and-tune.md` documents `--clear`. Audit r3: discharged |
| 11 | Code: valid JSON `null` reported as unparseable input (Minor) | not fixed; follow-up |
| 12 | Test: ordered-error test exercises only one unordered field (Minor) | not fixed; follow-up |

All 10 round-1 findings were verified CONFIRMED (9 codex verifier clusters), and the two round-2 findings were verified CONFIRMED.

### Bite-proofs

**Record:** `plugins/superheroes/lib/tests/bite_proofs/wo_vet_checks_json_key_1238.md`. It holds 18 guarded elements (E1–E18), each red on its axis with the exact red quoted, then reverted, followed by one combined green run (25 passed) on the final code head `5ced489f` in a detached probe tree. Accepted disclosures:
- **E10:** the first neutralization went red on the wrong axis (a KeyError). It was re-done so the malformed value reaches the disk writer.
- **E14:** proven against the destructive regression, because removing the explicit check alone is covered by the JSON-parse refusal.

The implementer's own record ran only E1. I replaced it with my final-head runs, which makes the record orchestrator-authored.

<!-- superheroes:degradations -->
### Disclosed degradations

- **One external reviewer family.** Promised: a mixed-vendor panel. Delivered: every review seat on codex (the maker cursor was excluded; the claude seats were pinned to codex per the issue order). Why: the issue's order.
- **Control probe `plant-undetected`.** Promised: an engaged, detecting canary. Delivered: an engaged canary that missed the plant. Why: model miss on a single sample.
- **No certification record.** Promised: a signed certification of the review loop. Delivered: the driver verdict `converged` / `audited-chain-degraded`, with the certification writer refusing `unrun-review`. Why: synthesis can only run as a native Claude subagent (registry cell claude-only; runner refuses the synthesis role), so it carries no execution evidence.
- **r3 step 2 orchestrator-typed.** Promised: the full lane delegates all implementation. Delivered: I applied the three-line docs substitution myself (`8949f100`). Why: the advisor's order gave the exact text; there was no design choice left for an implementer. The cursor seat reviewed it.
- **r3 reviewed by one seat.** Promised: independent review of every change. Delivered: one cursor seat. Codex came back `vacuous` on the docs-heavy delta, which the order anticipated. Why: the advisor's r3 order sets that review floor. The seat's `investigated` list names files, not a per-check outcome.
- **Judgment gate owner-unattributed.** Promised: an owner ruling on a tradeoff finding. Delivered: the gate's fail-closed default (`fix-as-suggested`). Why: the owner was absent during the unattended run.

### Dispatch provenance

| Dispatch | Engine / model (registry-gated) | Maker family | Rework | Blocking-finding attribution |
|---|---|---|---|---|
| Brief check | codex `gpt-5.6-sol` xhigh (`brief-check`) | n/a | no | n/a |
| WO-A code + tests + record | cursor `composer-2.5` (`implementer`, effort null) | xai | no | #5, #3/#4, #6, #8, #9: **order quality** (the order specified empty-stdin-clears, `[]`-removes, and "reason set → unreadable" for absent; it named no axis lines; it did not enumerate multi-line fields). #1/#2 and #12: **implementer execution** |
| WO-B docs | cursor `composer-2.5` (`implementer`) | xai | no | none |
| WO-C integration fixes (helper vocabulary, subprocess CLI test, doc wording) | cursor `composer-2.5` (`implementer`) | xai | yes (orchestrator integration read) | none |
| Review panel r1 (5 lenses) | codex `gpt-5.6-sol` xhigh (`reviewer-deep`, pinned) | n/a | n/a | n/a |
| Verifiers r1 (9), r2 (2) | codex `gpt-5.6-sol` xhigh (`verifier`) | n/a | n/a | n/a |
| Synthesis r1, r2 | claude opus (native subagent; the registry's only synthesis cell) | n/a | n/a | n/a |
| Control probe r1 | codex `gpt-5.6-sol` xhigh | n/a | n/a | n/a |
| Fixer r1, r2 | cursor `composer-2.5` (`code-fixer`, `--timeout 1800`) | xai | review-loop fixes | #10: **implementer execution** (the r1 fix changed CLI behaviour without its doc) |
| Audits r2 (5), r3 (3) | codex `gpt-5.6-sol` xhigh (`auditor`) | n/a | n/a | n/a |
| Scoped finder r2, r3 | codex `gpt-5.6-sol` xhigh (`reviewer-deep`) | n/a | n/a | n/a |
| Bite-proofs, gates | orchestrator (Claude Opus 5.5) | anthropic (receipts only; no product code typed through r2) | n/a | n/a |
| r3 step 2 docs substitution (`8949f100`) | orchestrator (Claude Opus 5.5), typed | anthropic | no | none |
| WO-r3 validator + tests (`ce922817`) | claude native subagent `sonnet-5` high (`implementer`, gate `effort_source: default`) | anthropic | no | none |
| r3 seat, codex | codex `gpt-5.6-sol` xhigh (`reviewer-deep`) | n/a | n/a | terminal `vacuous` |
| r3 seat, cursor | cursor `cursor-grok-4.6` xhigh (`reviewer-deep`) | n/a | n/a | 0 findings |

Maker families across the PR are now **xai** (WO-A–C and the fixers) and **anthropic** (r3). The r2 panel was codex-only, which excludes both. The r3 seat was cursor/xai, which excludes the r3 makers (anthropic).

Browser/test-pilot probe: **N/A**, since this plugin build has no running app. The receipts above stand in for it.

### Follow-ups for the advisor

- The Minor finding: `write-vet-checks` reports valid JSON `null` stdin as `vet-checks-input-unparseable`. It should be `vet-checks-malformed` / `vet-checks-not-a-list`.
- The Minor finding: `test_validate_vet_checks_multi_problem_ordered` exercises only one unordered field.
- The schema-version bump that makes older builds refuse a v2 profile rather than drop `projectConfiguration` / `vetChecks`. This is the existing WORKAROUND's delete-when, and it is release-coupled.
- Driver machinery:
  - synthesis has no evidence-bearing dispatch path (claude-only registry cell, runner refuses the role), so every driver session that reaches synthesis ends with a certification `unrun-review` refusal;
  - the certification writer also cannot bind audit rulings. Audits were landed as bare payloads, per the known C14 limit.

</details>

🤖 Generated with [Claude Code](https://claude.com/claude-code)



