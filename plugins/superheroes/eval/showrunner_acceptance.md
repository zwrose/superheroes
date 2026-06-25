# Showrunner per-issue Workflow spine (thin slice) — acceptance evidence

Work-item `showrunner-per-issue-workflow-spine-thin-slice-b70916` (issue #21, epic #85).
This is the recorded evidence for the spec's definition of done.

## Scope of this proof (read first)

This is the **thin proof slice** (the approved Discovery framing): it proves that the
control-flow-only `lib/showrunner.js` Workflow **composes** end-to-end over the existing
substrate libs via the `#86` `cmdRunner`/leaf bridge, and that every per-phase **judgement**
is a pure Python decider. Proof is delivered at two levels, both reproducible and CI-or-node
runnable:

- **Composition** — the `#86` stub-leaf node harnesses (`lib/tests/showrunner_*_smoke.js`):
  inject the `agent()`/`parallel()`/`log()` globals, `require` the real `showrunner.js`, and
  assert the orchestration wiring (which terminal, which fan-out, which park). Dev-time
  (`node`), not CI — matching the `#86` `review_panel_harness.md` precedent.
- **Unit** — the pure deciders under pytest (`lib/tests/test_*.py`), CI-gated. The judgement
  lives here; `showrunner.js` only forwards it.

**Deliberately deferred (not a gap):** a *live, production-style* unattended invocation — the
Workflow run as a registered `meta`-carrying Workflow over real leaf agents, creating a real
discardable PR — is **out of the thin-slice scope**. The owner-approved framing is that the
Workflow "can be not invoked in production until everything is deepened, and the current path
stays untouched." Wiring the real leaf agents, the production entrypoint, and the auto-fix
loops is the **deepening** tracked by #87–#90. So below, each DoD demo is backed by its
composition + unit evidence; where a demo's verb is "run it live," the evidence is the
composition harness that exercises that exact control-flow branch plus the unit test that
proves the decision, and the live-invocation boundary is called out. **No run transcript in
this file is fabricated** — every command below is reproducible as written.

## How to reproduce

```bash
# Unit (CI lane) — the deciders and lib touches:
python3 -m pytest plugins/superheroes/lib/tests/ -q          # 830 passed

# Full CI set (CLAUDE.md):
python3 .github/scripts/validate_marketplace.py
python3 .github/scripts/validate_hosts.py
python3 .github/scripts/validate_skills.py
python3 -m pytest .github/scripts/tests/ plugins/superheroes/lib/tests/ \
  plugins/superheroes/eval/tests/ eval/lib/tests/ -q          # 1006 passed

# Composition (dev-time, node) — the stub-leaf harnesses:
node plugins/superheroes/lib/tests/showrunner_reviewcode_loop_smoke.js
node plugins/superheroes/lib/tests/showrunner_reconcile_smoke.js
node plugins/superheroes/lib/tests/showrunner_startup_gate_smoke.js
node plugins/superheroes/lib/tests/showrunner_reviewcode_smoke.js
node plugins/superheroes/lib/tests/showrunner_ship_smoke.js
node -e "require('./plugins/superheroes/lib/showrunner.js')"   # loads clean
```

## DoD demo → evidence map

### Demo 2 — full pipeline to a parked, ready-for-review, non-merged PR (FR-1, FR-2, FR-10, FR-11)

- **Pipeline composes end-to-end.** `showrunner.js` assembles the ordered `PHASES`
  (`plan → review-plan → tasks → review-tasks → build → review-code → draft-PR → mark-ready →
  ship`) and loads clean (`node -e "require('./plugins/superheroes/lib/showrunner.js')"`). The
  reconcile→startup-gate→loop→park control flow is exercised by `showrunner_reconcile_smoke.js`
  (`OK: reconcile park_gate -> parked`) and the per-phase loop branches by the other smokes.
- **FR-1 content-addressed branch.** The build leaf (`build_entry.py`) derives the branch
  `superheroes/<work-item>-<content-hash>` from the approved tasks doc via the shared
  `docload.content_hash_for` (§6.3). Parity is unit-proven by `test_docload.py`, and was
  exercised for real by *this* work-item's own workhorse build, whose branch hash
  `fed7cb4dd1a17752` byte-matches `docload.content_hash_for` over `tasks.md`.
- **FR-2 never merges.** Structural: no `gh pr merge` (nor any `gh`/GraphQL merge form) appears
  anywhere in `showrunner.js` or any leaf. `grep -rnE "pr +merge|gh.+merge"` over the pipeline
  returns nothing. The terminal `shipPhase` parks; merge is the owner's.
- **FR-10 mark-ready precedes the CI read; FR-11 not merge-ready unless up-to-date AND green.**
  `shipPhase` orders `freshness.decide` → `ci` and returns `merge-ready` **only** when the
  branch is `up_to_date` **and** CI is `green`; any other freshness/CI result `park`s (not ready).
  `showrunner_ship_smoke.js` asserts the park path (`OK: ship parks (not merge-ready) when CI
  cannot go green`). `mark-ready` is its own phase ordered before `ship`'s CI read.
  **Honest CI in the slice:** because this slice does **not** read real CI (deferred to #87–#90),
  `ship_phase.py --step ci` returns an explicit `unverified` decision — never a false `green` — so
  the slice **parks honestly** ("CI not verified in this slice — confirm checks are green before
  merge") rather than posting a `merge-ready: CI green` signal it cannot substantiate. The
  `merge-ready` path is reachable only once a real CI read is wired (the `failing`/`ci_loop.decide`
  seam is kept in `ship_phase.py` for that deepening).

### Demo 3 — kill/relaunch: no duplicate PR, no re-flip (FR-3, FR-4)

- **FR-3 resume skips completed phases.** `showrunner()` resumes at `Number(from_step) + 1`
  (the phase after the last recorded cursor); front-half resume is unblocked by the
  front-half-aware `recover.reconcile` (skips the content-hash gate pre-branch) — unit-proven
  by `test_recover_front_half.py` (`continue` with no branch; still `gate`s in the back-half).
- **FR-4 record-before-advance + exactly-once PR / idempotent re-flip.** `recordCursor` writes
  `lastGoodStep` (+ the `{pr}`/`{ready}` side effect) **before** the loop advances. The draft-PR
  decision is the already-tested `recover.pr_action` (adopt an existing open PR / create exactly
  one / gate a merged-or-unknown read) — `test_recover.py`. The mark-ready decision is
  `pr_phase.mark_ready_action`: an already-non-draft PR → `skip` (no re-flip), a missing/None
  `isDraft` → `gate` — unit-proven by `test_pr_phase.py`.

### Demo 4 — changes-requested park, park-on-assumption, park-on-low-confidence (FR-6, FR-7, FR-8)

- `phase_step.decide` is the single decider; `test_phase_step.py` proves all six terminals and
  the **safety ordering** (assumption / low-confidence are evaluated *before* the gate, so they
  win even over a parking gate): `park_assumption` (FR-7), `park_low_confidence` (FR-8),
  `park_changes_requested` (FR-6), plus `park_pending` / `park_unexpected_gate`.
- Composition: `showrunner_reviewcode_smoke.js` proves a blocking panel verdict maps to
  `changes-requested` (`verdictToGate`). That a non-`proceed` action then parks is established by
  the `runPhases` loop body (`if (decision.action !== 'proceed') return { outcome: 'parked', … }`)
  together with the `phase_step.decide` park terminals (`test_phase_step.py`) and the
  `showrunner_reconcile_smoke.js` park path — not by `showrunner_reviewcode_smoke.js` itself, which
  asserts only the `verdictToGate` mapping.

### Demo 5 — UFR-1 startup refusal, UFR-2 durable-write park, UFR-4 readout fallback

- **UFR-1.** `showrunner_startup_gate_smoke.js` (`OK: UFR-1 — unapproved (pending) spec refuses
  to run`): a `pending` spec gate routes through `phase_step.decide` → `park_pending` at the
  `startup` phase, before any phase work.
- **UFR-2.** `journal_entry.py` catches `journal.DurableWriteError` and returns `{ok:false}`;
  `runPhases` turns a false `ok` into a park (`durable write failed … UFR-2`) with completed
  phases intact. The durable append/roundtrip is unit-proven by `test_journal_phase_record.py`.
- **UFR-4.** `readout_post.py` always records a durable `parked` event first; on a failed PR
  post it writes the readout to the store (`resume_brief`) and surfaces the error — never
  silently dropped (the `except` fallback branch).

### Demo 6 — review-code panel re-validates green, no regression (FR-16)

- `showrunner.js` consumes `review_panel_shell.js` **verbatim** (`require('./review_panel_shell.js')`,
  no fork). The deterministic gate/terminal/precedence matrix is unchanged and CI-green:
  `test_panel_tally.py` → 30 passed. The on-demand agentic-wiring harness is unchanged
  (`eval/review_panel_harness.md`). The review-code panel composing inside the Workflow is
  proven by `showrunner_reviewcode_loop_smoke.js` (the #89 deepening: the 5-reviewer panel
  driven across every terminal — the single-pass derisk smoke it supersedes was retired).

### Demo 7 — full band suite green, no regression (NFR)

- `python3 -m pytest .github/scripts/tests/ plugins/superheroes/lib/tests/
  plugins/superheroes/eval/tests/ eval/lib/tests/ -q` → **1006 passed** (baseline 809 in
  `lib/tests/` → **830** here; +21 across the full set).
- `validate_marketplace.py`, `validate_hosts.py`, `validate_skills.py` → all ✓.

## FR-15 (never writes the issue body)

Structural, like FR-2: `grep -rnE "issue +edit|issue.+body|gh issue"` over `showrunner.js` and
all leaves returns nothing. The run surfaces state only via the scrubbed PR `readout` /
`pr_comment` path (`readout_post.py` → `pr_comment.upsert(pr, "results", …)`).

## Throwaway-vehicle note

The spec's test vehicle is a **throwaway** work-item; per the approved framing the proof is the
recorded evidence above, not a retained change. Because the live production invocation is
deferred (see Scope), no throwaway PR was opened against the repo — opening/closing one would be
GitHub churn for evidence the composition + unit layers already establish. When #87–#90 wire the
real entrypoint, the live unattended run (open → ready → green → discard) becomes the natural
acceptance for that deepening.

## Native front-half (#88) — evidence map

The front-half phases are proven at the same two levels as the spine slice (composition smokes +
pure-decider unit tests); the live switched-on production run stays deferred to the controller era
(#22–#24), exactly as the #21 slice scoped.

- **Pure deciders (CI lane).** `front_half.gate_for_terminal` / `is_usable_draft` / `render_run_outcome`
  / `merge_findings` / `record_deferred` / `append_notify` are unit-proven both branches by
  `test_front_half.py`; the content-bound completion signal by `test_front_half_usable.py`. The
  `author` model role is proven by `test_model_tier_resolve.py::test_author_role_resolves_to_opus`.
- **Composition (dev-time, node).** `showrunner_fronthalf_panel_smoke.js` (the panel-doc leg wires the
  five reviewers + merge/synthesis/tally), `showrunner_fronthalf_phase_smoke.js` (terminal→gate map +
  idempotent passed-gate skip + the gate-write guard), `showrunner_fronthalf_produce_smoke.js` (produce
  resume / re-produce / park / notify — the produce-without-review seam), `showrunner_fronthalf_switch_smoke.js`
  (opt-in routing + the boundary park + the unchanged switch-off path, FR-9), `showrunner_fronthalf_boundary_smoke.js`
  (FR-7: the run-outcome envelope is composed via `render-outcome`, not dead code),
  `showrunner_fronthalf_extras_smoke.js` (the D-4 extras transport).
- **FR-7 boundary realized.** With the switch on, a passed `review-tasks` returns
  `{outcome:'parked', phase:'front-half-boundary'}` (the rendered run-outcome envelope embedding each
  phase's #104 readout) and the run never begins Build — proven by the switch + boundary smokes.
- **Consume-not-fork (FR-2).** No loop-decision logic (terminal vocabulary, circuit breaker, panel
  synthesis) lives outside the `reviewPanel` call-site; `showrunner.js` `require`s `review_panel_shell.js`
  verbatim.
- **Switch-off unchanged (FR-9).** With `SUPERHEROES_FRONT_HALF` unset, `showrunner` injects no
  front-half deps and every pre-existing smoke + the full pytest suite pass untouched.

## #89 — native review-code deepening (consumes #104)

The `reviewCodePhase` is now the code-review consumer of the shared loop. Evidence, two levels:

- **CI-gated pytest (the deterministic cores):**
  - config (FR-3/FR-7): `python3 -m pytest plugins/superheroes/lib/tests/test_review_code_config.py -q`
  - mechanical merge (FR-8): `python3 -m pytest plugins/superheroes/lib/tests/test_merge_findings.py -q`
  - deferral + parentOrigin extras (FR-6/FR-8): `python3 -m pytest plugins/superheroes/lib/tests/test_record_deferred.py -q`
  - multi-phase parentOrigin readout (FR-6): `python3 -m pytest plugins/superheroes/lib/tests/test_loop_readout.py -q`
  - the loop's own deciders (unchanged, still green): `python3 -m pytest plugins/superheroes/lib/tests/test_panel_tally.py plugins/superheroes/lib/tests/test_ship_gate.py plugins/superheroes/lib/tests/test_model_tier_resolve.py -q`
- **Dev-time node smokes (the JS control-flow):**
  - the consumer across every terminal + the UFR-2 covers-stamp park:
    `node plugins/superheroes/lib/tests/showrunner_reviewcode_loop_smoke.js`
  - the shared-shell extras seam: `node plugins/superheroes/lib/tests/showrunner_panel_shell_smoke.js`

Each DoD acceptance maps to one of the above: each terminal reached through the consumer's leaves
(smoke 1), the fail-closed negative path ending non-`clean` (smoke 1, scenario 5), the model tiers
(test_review_code_config), the `parentOrigin` halt naming the phase (test_record_deferred +
test_loop_readout + smoke 1, scenario 3), and the X′ covers stamp on `clean` (test_ship_gate + smoke 1,
scenario 1). The live, production-style invocation remains the deepening boundary called out above.
