---
kind: investigation-record
status: frozen
date: 2026-08-23
workItem: verification-strategy-for-the-superheroes-repo-c629cd
issue: 1105
title: Verification-strategy investigation — the superheroes repo's own suite, gates and history
---

# Verification-strategy investigation (2026-08-23)

> Frozen investigation record for [#1105](https://github.com/zwrose/superheroes/issues/1105).
> It imports the **foundational, project-independent** layer of the weekly-eats investigation
> (frozen at `docs/decisions/audits/2026-08-18-verification-strategy-investigation.md` in
> [weekly-eats-hq/weekly-eats](https://github.com/weekly-eats-hq/weekly-eats), kicked off by
> [weekly-eats-hq/weekly-eats#1109](https://github.com/weekly-eats-hq/weekly-eats/issues/1109)),
> re-measures everything project-specific on this repo's own history, and gives each of the
> issue's four hypotheses an explicit verdict on cited evidence. The policy itself is the
> work-item's `spec.md` beside this file — its approval is recorded by its own gate, not here.
> Every number carries its method and caveats; nothing was estimated silently. Raw ledgers,
> scripts and the full Leg-A delta report live in the owner's evidence bundle at
> `~/.claude/wave-logs/issue-1105-verification-investigation/` (`legA/`, `legB/`).
>
> **Consent record.** Investigation spend was authorized by the owner in the discovery session
> on 2026-08-23 ("yes to both, go ahead"): Leg B (~3–4 h, Sonnet fan-out, Fable synthesis) and
> the Leg-A delta (~45 min, Opus). Both closed inside their bounds. Model split, owner-approved
> the same day: Sonnet for mechanical measurement legs, Opus for open-ended research, Fable for
> the judgment seats (classification spot-checks, licensing checks, verdicts, this record).

## 0. Headline findings (plain language)

1. **CI time is volume, not a tail.** The pytest step is the whole gate (median 308 s since
   2026-08-15; every validator and install step is ≤3 s). The slowest single test is 31 s, so
   the 5-minute wall is ~12,500 collected cases running on one 4-core runner, not a few bad
   files. The lever is *how much runs per iteration*, not deleting slow tests.
2. **Pre-existing tests almost never catch anything at CI — and when they do, it is a rail.**
   In the repo's complete history (2,623 runs, 77 days, logs fully retained) exactly **4
   pre-existing test files** ever went red on a change they did not author; all four are
   census / drift / manifest-consistency rails. **Zero ordinary behavior tests** have ever
   caught a regression at CI. This is a floor (local runs hide catches), but it is the
   entire CI record.
3. **What CI actually catches is the builder's own broken new test.** 878 of 994 red
   (run × test) rows are birth-red — the PR's own new or modified test failing on push.
   Among branches whose first failure was a pytest failure, 77% had their own new test red
   on the first push. CI is functioning as the builder's first local run.
4. **The suite is majority behavior tests, not majority rails.** Rails are **53 of 259 files
   (20%), 21k of 152k LOC (14%), ~8% of test functions** after hand-correction of the
   mechanical census (which had said 56% / 66% by matching product modules named
   `guardian_*` and any fixture-reading test). The issue's premise that this suite "may be
   majority rails" is refuted; the rail layer is sizable, minority, and the only layer with
   a CI catch record.
5. **Defects here are found in the field, not by tests.** 36% of all merged PRs are
   `fix:`/`revert:` commits (45% in July). The twelve dated escapes in the qualitative
   ledger were surfaced by live runs, field use of a later build, an owner-commissioned
   audit, or repeated incidents — none by a pre-existing test. The weekly-eats-style loose
   escape floor (a fix citing a PR merged ≤7 days earlier) reads 13–17% of merges here vs
   4.6% there, but the method over-matches in this repo (PR bodies cross-cite constantly),
   so that number is a bounded floor, not a rate.
6. **Flakes are rare and well-handled; infra reds are rarer still.** Flake rate 0.30% of
   executions (8 events, 5 of them one known process-group family); 2 infra reds (the
   Claude CLI 2.1.237 install incident). No quarantine, every flake has an issue, all closed
   within days. The copytree-vs-`maintenance.lock` race named in memory has **never**
   manifested in a retained CI log.
7. **The calibrated local gate and the written policy disagree with each other and with
   practice.** The live `verifyCommand` is the four validators (no pytest) on a project venv
   running **Python 3.14.6**; CLAUDE.md's quoted block runs the full suite on `/usr/bin/python3`
   **3.9.6**; CI runs **3.12**; a memory note says the calibrated command "now runs pytest".
   Builders in practice run the full suite locally anyway. Three interpreters are in play
   and no drift test connects any of these homes. Separately, the project's storage-mode
   registry says `global` while the confirmed doc-policy says in-repo committed — found
   while placing this record.
8. **Six known false-green channels, zero mechanical tripwires.** Python-version skew, engine
   binaries on PATH, git identity in temp repos, stale Apple bytecode, pre-satisfied gates,
   sanitized-view stripping — each has bitten, each lives only in memory notes or a documented
   flag. The owner's own "named risks get mechanical tripwires" rule is unmet for all six.
9. **Maintenance surface is real but not the weekly-eats shape.** No seed-literal class
   exists here; the analogous classes are **count pins** (663 `len(...) == N`), **byte-pinned
   prose asserts** (150, in 46 files), and one true golden-fixture file. Structural can't-bite
   tests: effectively none (33 weak no-raise tests, 0 tautologies, 0 mock-shape-only, 0
   permanent skips). The suite is tidy; its cost is size and pins, not dead tests.
10. **The literature has nothing new since 2026-08-18, but the Python delta matters:** no
    Stryker for Python (mutmut ≥3.10 is the pick; it cannot run on the 3.9.6 local
    interpreter); no maintained linter detects can't-bite classes; `uv run --python 3.12` is
    a near-free cross-version receipt; and the markdown half of this product has a
    first-party eval framework (Anthropic skill evals, blind comparator) the TS record had
    no reason to surface.

## 1. Scope, method, what could not be measured

- **Window.** Complete CI history 2026-06-07 → 2026-08-23 (2,623 `ci.yml` runs; **every**
  failed-step log still retained — oldest run 77 days old, inside GitHub's 90-day retention;
  zero runs hit an expired-log wall). Suite snapshot at `dfa55243` (main, 2026-08-23).
- **Legs.** A-delta: Opus research agent, ~19 web calls, sources graded strong / medium /
  weak. B1: CI history via `gh api` runs / jobs / attempts, all 2,623 runs, all 137 red
  events' logs read. B2: static census over the four CI suites (`pytest --collect-only`,
  AST walks, regex); CI `--durations=25` tails from the 10 most recent green runs. B3:
  (run × failing test) attribution against each PR's changed-file list, tracebacks read
  individually; escape mining by targeted phrase patterns plus a full read of
  [#183](https://github.com/zwrose/superheroes/issues/183). B4: policy-vs-practice over
  CLAUDE.md, the calibration store, skills, rubrics, memory, and 15 recent PR bodies.
- **Timing source.** CI only. Local timing on the shared machine is unreliable (memory
  `gotcha-local-timing-unreliable-shared-machine`) and no local suite was run for this
  record.
- **Synthesis corrections applied to agent output (stated so the record is honest):**
  the B2 rail census was re-done by hand (§4.3) after spot-checks showed its heuristic
  over-classified; the B3 mechanical file-diff rule was corrected by traceback reading
  (it would have overstated catches 3.6×); the escape floor was computed fresh (§4.7).
- **Not measurable from artifacts:** local verify catches (builders fix red before pushing);
  review-panel wall-clock (every PR body counts rounds and seats, never minutes); work-order
  compliance with the targeted-files rule (no order artifacts are committed); the true
  escape *rate* (commit bodies use "fix" and "regression" as repo jargon, see §4.7).

## 2. Suite census at HEAD (`dfa55243`)

| Suite | Files | Collected cases | Test LOC | Product `.py` files / LOC | Test:product |
| --- | ---: | ---: | ---: | ---: | ---: |
| `.github/scripts/tests/` | 11 | 209 | 2,198 | 7 / 1,613 | 1.36 |
| `plugins/superheroes/lib/tests/` | 238 | 12,208 | 147,952 | 145 / 79,564 | 1.86 |
| `plugins/superheroes/eval/tests/` | 6 | 80 | 1,205 | 4 / 1,147 | 1.05 |
| `eval/lib/tests/` | 11 | 78 | 628 | 2 / 122 | 5.15¹ |
| **Total** | **266** | **12,575** | **151,983** | **158 / 82,446** | **1.84** |

¹ small-denominator artifact. Prose product (skills, rubric, agents, reference): 72 files /
15,205 LOC; folding it in gives 1.56, directional only. `lib/tests/` is 97% of cases and LOC;
by topic: pilot 29.9k LOC, guardian 20.5k, round_driver 14.7k, dispatch/engine 13.4k, launch
11.2k. Method: non-blank LOC; `--collect-only` counts parametrized cases individually (259
`test_*.py` files; 266 includes helper modules). 9,393 `def test_` functions.

## 3. Leg A — import register

Each imported claim is used only after its **licensing condition** was checked against this
repo. Source: the weekly-eats record §3 (full Leg-A report in that repo's bundle) plus the
delta report `legA/legA-delta.md` in this repo's bundle.

| # | Imported claim (weekly-eats §3 / delta) | Licensing condition | Holds here? |
| --- | --- | --- | --- |
| A1 | Economics inverted: scarce resources are gate latency × runs, flake surface, refactor tax; mainstream prescription is shrink-what-runs, not delete | A repo where agents write nearly all tests | **Yes** — 63% median test share of added lines over the last 60 PRs (§4.6) |
| A2 | Mutation testing is the one hard-evidence instrument on AI-written test quality; incremental per-PR + scheduled full | A Python tool exists and can run on an available interpreter | **Conditionally** — mutmut 3.7 needs ≥3.10: runs in CI (3.12) and the calibration venv (3.14), not on `/usr/bin/python3`; no `--diff` flag, wrapper needed; xdist composition unproven; covers only the Python libs, not the markdown product |
| A3 | Static import-graph test selection misses disk-read / config / subprocess couplings; safe form is path-placement with an always-run set and fail-open to full | The suite reads non-Python files | **Yes, amplified** — the product *is* markdown + JSON manifests and the validators run as subprocesses; coverage.py is blind to all of it. testmon ≥1.4 now composes with xdist, but the fail-open trigger list must include `*.md`, `*.json`, `rubric/`, `.github/scripts/` or selection is unsound on the highest-value change class |
| A4 | Flakes: ~2% mainstream threshold; blanket retries harmful; agent-specific gap argues tighter | Flake incidence is measurable | **Yes** — measured 0.30% (§4.3); the repo already forbids blanket retries in practice (no `--reruns`) |
| A5 | Tiered gates; for a one-owner repo the saving is on re-runs during a build | Multiple runs per PR | **Yes** — mean 4.8 / median 3 runs per PR; CI-minutes per PR median 8, p90 36 (§4.1) |
| A6 | Property-based / contract testing narrow; Pact-style contract testing n/a to a single app | — | **N/A** — no service boundary; the repo's contract register (CONVENTIONS §11) is its own contract instrument; the +9.8 pp spec-driven test-generation result (arXiv 2608.17177, 2026-08-17, strong) supports that ordering without stretching |
| A7 | Deletion: redundancy improves catch rate; sharp criterion is structural cannot-fail; LLM suites keep 18% of tests through a pure refactor | The suite has structural can't-bite tests to find | **Mostly absent** — 0 tautologies, 0 mock-shape-only, 0 permanent skips (§4.5); the July rewrite (−55.8k test lines) is the refactor-tax specimen |
| A8 | Agent-trust rails: fitness functions, invariant tests routed to a human, shadow → gating | — | **Yes, this is the product** — and the only layer with a CI catch record (§4.4) |
| A9 | Visual/board conformance | A UI | **N/A** |
| A10 | Weekly-eats 44% mocked-route-vs-real-DB redundancy | A DB and a mocked layer over it | **Does not port** — no DB. The analogous redundancy class here is **doc↔code drift tests that pin the same fact from both sides** (count pins + byte-pinned prose, §4.5); not measured as a redundancy rate, named as the class to assess |
| A11 | Weekly-eats numbers (1% flake budget, 4.6% escape baseline, 8-min bar, 30-observation window) and rulings (single-flake blocks, no quarantine, narrow deletion mandate) | — | **Do not port** by the issue's rule; re-derived or re-decided in the sitting (§6) |
| A12 (delta) | Agents add mocks in 36% of commits vs 26% for humans; guidance belongs in agent config files (arXiv 2602.00409, strong) | Agent-authored tests | **Yes** — grounding for a mock-density rule in the rubric surface, though self-mocking measured here is tiny (4 hits / 3 files) |
| A13 (delta) | No maintained Python linter detects the four can't-bite classes; ~150 lines of AST in-repo | Willingness to own a validator over a declared grammar | **Yes** — safe because it validates Python AST, not prose (memory `gotcha-hand-rolled-validator-over-hand-editable-doc` does not apply) |
| A14 (delta) | `uv run --python 3.12 -m pytest` as the cross-version receipt; `vermin --target=3.9` static complement; or move local dev to uv-managed 3.12 and the exposure disappears | `uv` available locally | **Yes** — `uv` is already a CI dependency and test-pilot's |
| A15 (delta) | Anthropic skill evals (`evals/evals.json`, blind comparator, `claude plugin eval`, 2026-03-03) are the closest analogue to mutation testing for prose | Skills as product; token budget per case | **Yes, with cost** — applies to the markdown half nothing else measures; real per-case token cost |
| A16 (delta) | One-home-per-fact has no published grounding; justify by the duplication→drift mechanism | — | House rule (CONVENTIONS §11); stays, justified by §4.4's catch record, not by citation |

Nothing material was published 2026-08-18 → 2026-08-23 (arXiv cs.SE swept by submission date;
Anthropic / Cursor / OpenAI checked).

## 4. Leg B — the repo ledger

### 4.1 Gate time (B1)

Method: every `validate` job's steps for 2,620 of 2,623 runs (`gh api …/runs/{id}/jobs`,
selecting the job named `validate` — 1,952 runs carry a second, historical `pr-title` job
that would corrupt naive parsing). Successful-step medians.

| Step | n | median | p90 |
| --- | ---: | ---: | ---: |
| checkout / setup-python / install deps | 2,620 | ≤2 s | ≤5 s |
| each of the four validators | ≈2,000–2,620 | 0–1 s | ≤1 s |
| jscpd / dependency-cruiser / Claude CLI installs | 575–1,014 | 2–3 s | ≤6 s |
| **Run plugin + band-eval tests** (all history) | 2,496 | **103 s** | **389 s** |
| **Run plugin + band-eval tests** (since 2026-08-15) | 245 | **308 s** | **365 s** |

Median run wall by month: Jun **20 s** → Jul **105 s** → Aug **372 s** (p90 31 → 167 → 712 s),
~18.6× in ten weeks. Runs per PR: mean 4.81 / median 3 / p90 8 / max 48. CI-minutes per PR:
mean 15.5 / median 8.0 / p90 36.1; the most expensive PR (a release-please PR open for weeks)
cost 348 min; the most expensive feature PR 175 min over 35 runs. Runner: 100%
`ubuntu-latest`, 4 cores. Queue median 11 s.

**The wall is volume.** The slowest test is 31.2 s and the stable slow tail (22 tests present in
≥8 of 10 recent runs, all real `git worktree` / subprocess timing tests) sums to roughly 2–3
minutes of *per-worker* time across 4 workers; the rest of the 308 s is 12,500 cases. File-level
concentration like weekly-eats' "65% in ten files" does not exist here.

### 4.2 Per-file runtime

Not measured locally by design. CI's `--durations=25` tail (10 recent green runs,
`legB/ci-durations-tail-aggregate.csv`) is deterministic to within ±0.3 s per test:
`test_engine_dispatch_e2e.py` (3 × 31 s + 12 s ≈ 105 s), `test_launcher.py` (15.5 s),
`test_wave_watch.py` (9 s), twelve `test_launch_roundtrip.py` parametrizations (5–6 s each).
23 files spawn real `git worktree`s; the jscpd / depcruise seams are `skipif`-gated.
**Caveat:** only the top 25 are published; the body of the distribution is unmeasured at CI.

### 4.3 Rail census — hand-corrected (B2 → synthesis)

The mechanical census (`legB/rail-census.csv`: 144 files / 56%, 99.7k LOC / 66%) matched
`guard` in `test_guardian_*` (the Guardian is a product feature), `conformance` / `registry` /
`schema` in product-module names, and "reads a doc from disk" in any fixture-reading behavior
test. Six of six sampled "low-confidence rails" and the three largest "high-confidence rails"
(`test_round_driver.py`, `test_engine_dispatch.py`, `test_sanitized_view.py`) were ordinary
behavior suites. Per memory `gotcha-hand-rolled-ast-census-does-not-converge`, the set was
**pinned** rather than the grammar modelled: v3 = a file is a rail if it resolves the repo or
plugin root from `__file__` and asserts on **committed** files with few or no tmp fixtures, OR
its name carries `doctrine | _sync | drift | census | stub_markers | skill_shape | taxonomy |
ci_workflow | ci_collectors | guardian_conformance | release_config`, OR it has ≥15 committed-
tree references outnumbering tmp references (the two files that rule added were read and
confirmed). Result (`legB/rail-census-v3.csv`):

| | Files | LOC | Test functions |
| --- | ---: | ---: | ---: |
| Rails | **53 (20%)** | **20,992 (14%)** | **725 (8%)** |
| Behavior | 206 | 130,811 | 8,668 |

Largest rails: `test_ssot_drift.py` (4.3k LOC, 93 tests — CONVENTIONS §11 guards),
`test_spec_content_doctrine.py` (1.2k), `test_charter_boundary_sync.py` (1.1k),
`test_launch_chokepoint_census.py` (1.0k), `test_seat_tool_grants.py` (1.0k).
**Caveat:** v3 is a pinned set with a stated rule; files a future reader classifies
differently change the shares by a few points, not the conclusion.

### 4.4 Regression-catch ledger (B3 — the core)

Method: all **105** failing `pull_request` runs in history, 994 (run × failing item) rows,
each joined against the PR's final changed-file list, **every traceback read** (the mechanical
rule alone would have counted 29 git-identity infra rows as catches).

| Class | Rows | Runs |
| --- | ---: | ---: |
| birth-red (the PR's own new/modified test) | 878 | 54 |
| infra (runner git identity ×15 runs, npm install ×2, …) | 62 | 18 |
| validator-catch (non-pytest gate) | 37 | 32 |
| **regression-catch (pre-existing test, PR did not touch it)** | **10** | **9** |
| flake | 7 | 7 |

**Distinct pre-existing test files that ever caught a change they did not author: 4.**

| File | Rail? | PR | What it caught |
| --- | --- | --- | --- |
| `test_repo_root_census.py` | census | [#756](https://github.com/zwrose/superheroes/pull/756) | new module walked `.git` ancestors by hand instead of the sanctioned resolver |
| `test_ssot_drift.py` | drift | [#783](https://github.com/zwrose/superheroes/pull/783) | severity vocabulary updated in 7 of 8 homes |
| `test_calibration_root_caller_census.py` | census | [#943](https://github.com/zwrose/superheroes/pull/943) | new call site skipped `UnresolvableRootError` adjudication — the invariant guarding against a refusal masquerading as an uncalibrated result; red on 5 consecutive pushes |
| `test_release_config.py` | manifest consistency | [#48](https://github.com/zwrose/superheroes/pull/48) + 3 release PRs | release-please `extra-files` paths wrong, so `plugin.json` never bumped — predecessor of today's `check_release_bump.py` |

**Zero ordinary behavior tests have ever caught a regression at CI.** Floor caveat: local runs
hide catches; this is what reached CI. **Validator gates:** every validator that ever fired did
so in the repo's first three weeks (2026-06-19 → 07-08), except `check_release_bump.py` —
15 reds, a 100% hit rate on 3 real release-please parser-drop incidents, the one gate guarding
something no builder can verify locally. `validate_marketplace.py` has never fired.

### 4.5 Pins, can't-bite, redundancy (B2)

- **Count pins:** 663 `len(...) == N`; top files `test_engine_dispatch.py` (41),
  `test_guardian_sweep.py` (37), `test_round_driver.py` (32). 1,647 bare `== N` is a noisy
  upper bound (matches exit codes).
- **Byte-pinned prose asserts** (a ≥6-word literal `in` a document/output): 150 in 46 files;
  top `test_configure_view.py` (22), `test_guardian_lens_deps.py` (16).
- **Restated constants:** 1,207 coarse substring hits — a candidate list, not a defect count
  (most are error messages correctly pinned verbatim).
- **Self-mocking of the module under test:** 4 hits in 3 files — a lower bound by construction.
- **Golden fixtures:** 1 true file (`test_round_orders.py`, byte-for-byte dispatch-order text).
- **Structural can't-bite:** 33 no-assert tests (all "must not raise" — weak, not dead;
  15 clustered in `test_pilot_policy.py` / `test_pilot_contract.py`); **0** tautologies (2
  flagged, both determinism checks); **0** mock-shape-only; **0** permanent skips / xfails
  (35 `skipif`s, all environment-conditional).
- **Redundancy class:** no DB here, so weekly-eats' 44% figure does not port. The analogous
  class is a fact pinned from both sides (a drift test *and* a count/prose pin in a behavior
  test). Not measured as a rate; named for the cut list to assess.

### 4.6 Growth and proof mass (B2 + synthesis)

| Month | Commits | Test +/− | Non-test +/− | `fix:`/`revert:` share of merged PRs |
| --- | ---: | ---: | ---: | ---: |
| Jun | 61 | +26.9k / −1.4k | +42.1k / −6.0k | 8 / 57 (14%) |
| Jul | 287 | +104.4k / **−55.8k** | +88.3k / −59.5k | 128 / 287 (**45%**) |
| Aug (→23) | 155 | +113.3k / −3.2k | +67.5k / −6.5k | 43 / 155 (28%) |

Last 60 merged PRs: test share of added lines **median 63%, p90 83%**. July's −55.8k test lines
is the repo's one refactor-tax specimen (a test-tree rewrite/rename wave, 653 delete events
with 454 adds). 179 of 499 merged PRs (36%) are fix-typed.

### 4.7 Escapes (B3 + synthesis)

- **Loose floor, weekly-eats method** (fix/revert commit citing a PR merged ≤7 days earlier):
  **87 / 499 = 17.4%** (tightened to bodies naming a regression-shaped phrase: 65 / 499 =
  13.0%). **Over-matches here:** PR bodies in this repo cite related PRs as context routinely,
  and `fix:` is used for mid-build design tightening, not only post-merge defects. Carry as a
  bounded floor that is not comparable to weekly-eats' 4.6% without the same over-match.
- **Qualitative ledger** (`legB/escapes-ledger.csv`, 12 rows): 2 silently-degraded validators
  ([#815](https://github.com/zwrose/superheroes/issues/815): coupling-lens collectors never
  installed in CI, its positive control skipped silently on every run; an omission-floor drift
  guard that matched words anywhere in a document — missed 4 of 9 constructed drifts); 3
  flakes, each with an issue closed within days; 4 repeated-incident / no-layer-existed cases
  (the round_driver malformed-submit family hit three times in one week; a cleanup-binding hole
  that survived two narrow fixes; a manifest key confusion whose root PR shipped 10 days
  earlier; a `seat_map compose --pins` crash on documented input); 2 live-run-only escapes (a
  courier dropping bytes; a first-write CLI path no test had ever exercised — its fix commit
  says "escaped CI").
- **[#183](https://github.com/zwrose/superheroes/issues/183)** (2026-07-04) is the prior audit:
  27 fix PRs, 53 defects — rubric-gap 30, taxonomy-gap 10; escapes clustered in PRs with **no
  review-loop evidence**, the class the review-discipline rule then closed. This leg found
  **zero** review-skipped escapes since.
- **No shipped defect** in the window matches the "green locally, red in CI" channels
  (Python version, engine binaries); those cost build-loop time, not merged bugs.

### 4.8 Flakes and infra (B1)

137 red events (133 final-red runs + 4 attempt-1 reds hidden by manual re-run). Classes:
80 pytest/validator reds later attributed in §4.4, 26 cancelled-superseded, 15 release-gate-
expected (deterministic red while a release PR accumulates), 8 **flake** (0.30% of 2,634
executions), 6 pr-title-gate (all in the first three weeks), 2 **infra** (Claude CLI 2.1.237
install). Flake families: `test_launcher.py` deadline family (one event, 14 ids),
`test_engine_dispatch.py` abandon-order (load), `test_pilot_mint.py` / `test_pilot_*` PID-file
race ([#882](https://github.com/zwrose/superheroes/issues/882) — two earlier unfiled specimens
on 2026-08-03 and one new candidate in `test_pilot_mint.py`). The `maintenance.lock` race:
grepped all 133 failed logs, zero hits.

### 4.9 Policy vs practice (B4 + synthesis)

| Written rule | Home | Measured |
| --- | --- | --- |
| Calibrated local verify = four validators | `core.md` `verifyCommand` (venv, Python 3.14.6) | Matches CLAUDE.md's prose; contradicts CLAUDE.md's quoted block (full pytest on `/usr/bin/python3` 3.9.6) and memory (`gotcha-full-suite-exceeds-dispatch-attempt-cap`: "now runs pytest"). No drift test across the three homes |
| Full suite is CI's receipt | CLAUDE.md | Holds; builders also run it locally (PR [#1084](https://github.com/zwrose/superheroes/pull/1084) body) |
| Orders name targeted files, never the suite (900 s cap) | `dispatch-mechanics.md`, `engine_dispatch.py:89` | Not verifiable — no order artifacts committed |
| Every PR reviewed before handback | `rubric/review-discipline.md` | Holds in all 10 code-touching PRs sampled |
| Named risks get mechanical tripwires | owner rule (memory) | **Unmet for all six false-green channels** (§0.8) |
| One home per cross-boundary fact + drift test | CONVENTIONS §11 | Unmet for the verify-command fact and for the storage-mode fact (registry `global` vs policy in-repo) |
| Guardian suite vitals | `guardian/vitals.jsonl` | One record (2026-07-22: 156.8 s / 2,923 tests) — a sample, not a trend |

Review-panel spend is a **distinct cost class** from CI: every sampled PR body counts rounds
and seats (e.g. 5-seat then 3-seat cross-vendor rounds) and none converts to minutes.

## 5. Hypothesis verdicts

- **H1 (catch-rate vs cost) — CONFIRMED on catch-rate, with the rail exemption applied from
  the start.** 4 of 259 files have ever caught a regression at CI, all rails; 0 of 206
  behavior files. The behavior layer's cost is 308 s per run × ~5 runs per PR and a
  63%-of-added-lines maintenance surface. Its *expected* future catch rate is not zero —
  local catches are invisible (§1) — but the CI record gives it none. The cost is
  misattributed only in one sense: it is volume, not a slow tail.
- **H2 (gate shape) — SUPPORTED, with two corrections.** The "majority rails" premise is
  refuted (20% of files). The two-tier split that exists (four validators local, suite at CI)
  is not what builders do — they run the suite locally — and what CI mostly catches is
  birth-red, i.e. work the local run would catch if it ran. The safe fast tier is therefore
  **path-placed selection with the rail set always-on and fail-open to full on any non-Python
  change** (A3), never import-graph selection; the nightly/deep tier is where mutation and
  skill evals live.
- **H3 (misallocation) — CONFIRMED on the second half, open on the first.** The classes that
  produced real escapes — silently-degraded validators, first-write paths nothing exercised,
  repeated-incident surfaces, field-found crashes on documented input — have thin or no
  instruments, and the six false-green channels have none. Whether proof mass is *overweight*
  anywhere cannot be shown from catch history alone (rails are exempt from that scoring and
  behavior tests may catch locally); the count-pin and prose-pin censuses mark where the
  weight is, not that it is wrong.
- **H4 (density explains the low escape rate) — CANNOT BE REFUTED and constrains the
  change-set.** The escape floor is loose and over-matched; local catches are invisible; the
  literature says redundancy improves detection. Any cut must name its non-regression
  validation — here a standing catch/escape ledger with this repo's own classes, plus the
  bite-proof / cannot-bite evidence the repo already invented.
- **Unpredicted findings.** (i) The one validator that still fires guards the thing no
  builder can verify locally (release-please's parser). (ii) Three Python interpreters are in
  play, not two. (iii) The storage-mode registry and the doc-policy disagree.

## 6. Decisions the owner took in the sitting

_Recorded after the attended sitting; the normative statement is `spec.md` beside this file._

Attended sitting, 2026-08-23, in-channel; each ruling is the owner's own word on the option
presented, after the owner asked and was answered on how "most tests never catch anything at
CI" reconciles with "most tests stay" (CI is the last net, not the only one; catches are rare
events; the asymmetric risk favors keeping unassessed tests until a ledger says otherwise).

1. **Retention = can-bite** (bite-proof or mutation kill); rails exempt from history-based
   scoring, never from bite-proofing; unassessed tests stay. ("I'm good with A.")
2. **Three tiers, path-placed:** local = validators + the rail set always-on + owned-path
   behavior tests, fail-open to full on any non-Python change; merge = full suite at CI,
   unchanged; nightly = full suite + deep instruments; observation mode before selection is
   trusted. ("B.")
3. **Flakes:** a recorded flake blocks merges until fixed at its cause; no retries, no
   quarantine; budget tripwire 0.5% over a trailing 30 days, breach = owner decision.
   ("Sure b.")
4. **One Python everywhere, pinned in one home, drift-guarded**, `uv` the one installer;
   census tripwires for git identity and engine-binary assumptions; pre-satisfied gates and
   sanitized view stay practice rules. (Owner's own stronger statement of option a: "a
   single source of python everywhere, set up so it doesn't drift again.")
5. **Six authoring rules** carried by the test lens: no cannot-bite tests; no duplicate pins
   of rail-guarded facts; rails declared, bite-proofed, inventoried; fixes name what they
   fix; no proof-mass ratio; burndown when touched. ("All 6 as written.")
6. **Instruments now:** catch/escape ledger, mutation sweep, flake differential, vitals
   trend; skill evals a named candidate with its own spend approval. ("Good with your rec.")
7. **Deletion:** only cannot-bite with evidence; burndown when touched; bulk removal after
   ≥45 ledger days as a named checkpoint. (Confirmed with the framing.)
8. **Derived change-set lives in the spec as proposals; nothing is filed from this
   session** — routing to issues is a later session's work on the owner's word. ("You're not
   meant to file issues.")

Framing approved 2026-08-23 ("Write it up"). Full-weight review called by the owner the same
day ("Full").

**Post-review rulings (2026-08-23, after the cross-spec comparison):** (i) local receipts
follow the weekly-eats approach — PR-body at handback, no live ledger feed; observation and
flake visibility computed over handed-back receipts; unhanded-back local runs an accepted
invisible floor ("update ours to use their approach"). (ii) The advisor's competing
next-dispatch obligations carry **no precedence order** — the review panel's ordering was
removed by the owner's ruling ("I don't really care what order these get addressed …
keep theirs and apply it here"); the coincidence of obligations is an owner-accepted
residual, not a defect.

**Cross-spec reconciliation rulings (2026-08-24, differences 1–4):** (1) instrument-authority
fork ratified as one tier principle — gate-tier evidence blocks, instrument-tier evidence gets
a human first; neither spec changes ("a"). (2) Fix-naming: weekly-eats adopts this spec's
explicit pre-dates claim + vet check (prompt handed to that session). (3) Review-receipt
authenticity: weekly-eats adopts this spec's machine-written traceable receipts + nightly
check (prompt handed to that session). (4) Risk profile: this spec adopts a normative 5-row
risk profile (§ Risk profile, FR-4b), depth-follows-consequence, seeded from the escape
classes in §4.7. Also ruled: FR-9's receipt obligation attaches only with P3's gate driver,
never as a standalone build.

**Ruling by reference (2026-08-23):** on the review panel's three open policy questions —
flake-block authority and release conditions, escape-candidate attribution and baseline,
burndown bound — the owner ruled: *"if there is a way to make an equivalent ruling as what's
already encoded there [the weekly-eats spec], please do that; if there is still a genuine call
for me, please re-present it."* All three resolved by porting the weekly-eats shape
(FR-24a/24b/26a/26b, FR-19a/19b, UFR-6, FR-15/FR-18d of
`docs/superheroes/verification-strategy-for-an-ai-first-codebase-ear-f47285/spec.md` in
[weekly-eats-hq/weekly-eats](https://github.com/weekly-eats-hq/weekly-eats)) with this repo's
own numbers (baseline 17.4% by the mechanical rule, §4.7); no genuine call remained.

## 7. Receipts

- Bare cross-repo issue numbers: `grep -nE '(^|[^/a-z])#[0-9]+' investigation-record.md`
  returns only host-repo references written as full links — receipt recorded on freeze.
- Evidence bundle: `~/.claude/wave-logs/issue-1105-verification-investigation/` —
  `legA/legA-delta.md`; `legB/b1-ci-history.md`, `b2-census.md`, `b3-catch-escape.md`,
  `b4-gate-accounting.md`, `escapes-qualitative.md`; ledgers `ci-runs-ledger.csv`,
  `step-timing.csv`, `red-runs-ledger.csv`, `regression-catch-ledger.csv`,
  `escapes-ledger.csv`, `rail-census-v3.csv`, `pins-census.csv`,
  `cannot-bite-candidates.csv`, `growth_by_month.csv`, `pr_test_share.csv`,
  `ci-durations-tail-aggregate.csv`; scripts `01`–`06` and the rail v2/v3 scripts.
- Zero code, test, script or workflow changes on any branch from this issue.
