# Live single-issue showrunner — end-to-end acceptance evidence

Work-item `live-single-issue-showrunner-end-to-end-run-post-a-b6ea72` (issue #102, milestone
"Showrunner (run engine)", epic #85). This is the recorded evidence for the spec's definition
of done: the owner can approve a spec, choose "run the showrunner," walk away, and come back
to a ready-for-review pull request they only need to merge.

## Scope of this proof (read first)

This work turns the already-merged showrunner spine (#21) and its deepened phases — front-half
plan/tasks authoring (#88), build (#87), code review (#89), test-pilot (#90) — **on** for one
approved work-item. What #102 adds is the **launch path** (a deterministic pre-flight gate, a
self-contained Workflow-tool bundle, the `showrunner` skill), the **post-approval path choice**,
the **back-half deepenings** (the full-run boundary + a real CI read), the **superpowers cut**,
and the **codified readout** — proven at two levels:

- **Deterministic (CI lane).** The pure deciders and the canned-agent composition smokes,
  all green under `pytest` (the node smokes are wrapped by `test_showrunner_node_smokes.py`).
  These prove every per-phase **judgement** and the **control-flow** front-to-back, offline.
- **Live one-shot (manual).** A single owner/live-session run of the real Workflow over live
  leaf agents, opening then discarding a real pull request. This is the one step CI cannot
  perform (it needs a live session + `gh` against a required-checks repo); it is the marked
  manual acceptance step below.

**No run transcript in this file is fabricated** — every command below is reproducible as
written, and the live one-shot has an explicit slot to record its real phases + PR link.
The **durable, repeatable agentic acceptance** of the live run — re-running it as a gated,
recorded check rather than a one-time manual session — is **deferred to
[#112](https://github.com/zwrose/superheroes/issues/112)**, and the full superpowers removal
across the band to [#111](https://github.com/zwrose/superheroes/issues/111).

## How to reproduce (deterministic lane)

```bash
# Pre-flight + CI-status deciders (pure, fail-closed):
python3 -m pytest plugins/superheroes/lib/tests/test_preflight.py \
  plugins/superheroes/lib/tests/test_ci_status.py -q

# The FR-8 superpowers-free invariant (authoring leaf + generated bundle):
python3 -m pytest \
  plugins/superheroes/lib/tests/test_safety_invariants.py::test_showrunner_path_is_superpowers_free -q

# Composition smokes (dev-time node — wrapped into CI by test_showrunner_node_smokes.py):
node plugins/superheroes/lib/tests/showrunner_bundle_smoke.js
node plugins/superheroes/lib/tests/showrunner_fullrun_smoke.js
node plugins/superheroes/lib/tests/showrunner_fullpipeline_smoke.js
node plugins/superheroes/lib/tests/showrunner_ship_smoke.js

# Full CI set (CLAUDE.md):
python3 .github/scripts/validate_marketplace.py
python3 .github/scripts/validate_hosts.py
python3 .github/scripts/validate_skills.py
python3 -m pytest .github/scripts/tests/ plugins/superheroes/lib/tests/ \
  plugins/superheroes/eval/tests/ eval/lib/tests/ -q

# The superpowers-free bundle grep (must be empty):
grep -rnE "writing-plans|subagent-driven|superpowers" plugins/superheroes/lib/showrunner.bundle.js
```

## DoD → evidence map

Each Definition-of-done bullet (spec §"Definition of done / success") maps to a deterministic
demo backed by a real Tier-1 test/smoke, plus the marked live one-shot for the parts CI cannot
perform.

### DoD — the showrunner can be launched for real on an approved-spec work-item (FR-1, FR-9)

- **Production launch path exists.** The `showrunner` skill runs `lib/preflight.py` then invokes
  the **Workflow tool** on the committed `lib/showrunner.bundle.js`. The bundle **composes and
  executes in a no-`require` sandbox** (faithfully emulating the Workflow script sandbox) and
  exports a `showrunner` — `node showrunner_bundle_smoke.js`
  (`OK: bundle composes + executes in a no-require sandbox + exports showrunner`). A drift guard
  (`test_bundle_drift.py`) keeps the committed bundle byte-identical to a fresh emit.
- **Pre-flight runs before launch and stops on a failed check.** `preflight.decide` is the pure,
  fail-closed gate — an unapproved spec, missing `gh` access, a conflicting live run, an
  unready repo, or an unresolvable verify/config each blocks with a named cause + remediation;
  an indeterminate read is treated as not-passing. `test_preflight.py` proves all-pass→ok,
  unapproved-spec→block, indeterminate→fail-closed, live-run-blocks-but-stale/parked-passes, and
  the required-CI advisory suppression. The CLI shape (`preflight.py --work-item nope --root .`
  → `ok:false`, exit 1) is exercised in Task 6.

### DoD — the post-approval choice is offered and routes correctly (FR-1)

- **Discovery presents; the showrunner executes.** `architect-discovery` step 8 presents the
  two-option choice (showrunner recommended / manual bridged) with no default, records the
  advisory choice (`lib/path_choice.py`, round-tripped by `test_path_choice.py`), and on the
  showrunner pick invokes the `showrunner` skill; on the manual pick it falls through to the
  **byte-unchanged** hand-off (FR-3 lock — the preserved hand-off line is asserted in Task 13).
  The advisory record is non-authoritative; the run state wins (a never-started showrunner pick
  re-enters via the skill).

### DoD — a successful run hands back the codified readout (FR-10)

- **Full pipeline reaches a ready-for-review outcome.** `showrunner_fullpipeline_smoke.js` drives
  `runPhases` front-to-back in full-run mode (native authoring deps, **no** `frontHalfBoundary`)
  with canned per-phase agents and asserts the terminal outcome is `ready` at `ship`
  (`OK: full pipeline reaches a ready-for-review outcome (canned agents)`).
- **Full-run proceeds past the front-half boundary (FR-4).** `showrunner_fullrun_smoke.js` proves
  the loop enters Build instead of parking at the boundary when native authoring is injected and
  `frontHalfBoundary` is absent.
- **The ship terminal is honest (FR-5).** `showrunner_ship_smoke.js` asserts `green → ready`,
  `red → park`, and `none → ready-with-carve-out` (no required checks gate the PR → mark ready
  with the "confirm checks before merging" note, never a false green).
- **The readout assembles + projects.** `run_readout.assemble` maps run-end state onto
  `build_readout`'s context (PR link, CI status, built-vs-acceptance, test-pilot, merge reminder,
  all scrubbed); `run_readout.run_outcome` is the machine-readable projection #112 consumes —
  both unit-proven by `test_run_readout.py`.

### DoD — the showrunner path is superpowers-free (FR-8)

- **Impossible-by-construction, CI-enforced.**
  `test_safety_invariants.py::test_showrunner_path_is_superpowers_free` fails loudly if the
  authoring leaf (`eval/produce-leaf.md`) or the generated live bundle
  (`lib/showrunner.bundle.js`) names the superpowers toolkit. Task 17's bundle grep
  (`writing-plans|subagent-driven|superpowers` → empty) is the end-to-end confirmation. The
  manual bridged path keeps its superpowers dependency, untouched.

### DoD — full validation + test suite green, manual path free of regressions (NFR)

- The three validators (`validate_marketplace.py`, `validate_hosts.py`, `validate_skills.py`)
  pass, and the full pytest set (`.github/scripts/tests/`, `plugins/superheroes/lib/tests/`,
  `plugins/superheroes/eval/tests/`, `eval/lib/tests/`) — including the wrapped node smokes and
  the new deciders/smokes — is green (Task 17). The manual hand-off line is asserted byte-unchanged
  (FR-3, Task 13), so the manual bridged path carries no regression.

## Live one-shot (manual) — the one owner/live-session acceptance step

This is the **single step CI cannot perform**: a real, unattended run of the showrunner over
live leaf agents against a repo whose PRs are gated by required checks. Perform it once, record
the result below, then discard the throwaway PR/branch.

**Reproduce steps:**

1. **Mint a disposable work-item.** In a required-checks repo, run `architect-discovery` on a
   tiny throwaway idea and take it to spec approval (`gates.review == passed`).
2. **Pick the showrunner at the post-approval choice.** Discovery offers the two options; choose
   **"Run the showrunner (recommended)."** It records the advisory choice and invokes the
   `showrunner` skill.
3. **Watch pre-flight pass, then the run go.** The skill runs
   `python3 ${CLAUDE_PLUGIN_ROOT}/lib/preflight.py --work-item <wi> --root <root>`; on `ok:true`
   it reads `lib/showrunner.bundle.js` and invokes the **Workflow tool** with
   `args: {workItem: <wi>}`. Walk away.
4. **Confirm the hand-back.** The run drives plan → review → tasks → review → build → review-code
   → draft-PR → test-pilot → mark-ready → ship and **parks at a ready-for-review PR** once the
   branch is base-current and CI is **green** — it never merges. It prints the codified readout
   (PR link, CI status, built-vs-acceptance, test-pilot result, merge reminder).
5. **Record the evidence** in the slot below — the phases the run traversed and the PR link.
6. **Discard** the throwaway PR + branch (close the PR, delete the branch). The accepted GitHub
   churn is the cost of real end-to-end evidence (spec §Assumptions).

**Proof-run record (fill on the live one-shot):**

- Date / session: _<to record>_
- Repo + throwaway work-item: _<to record>_
- Phases traversed: _<plan → review-plan → tasks → review-tasks → build → review-code → draft-PR → test-pilot → mark-ready → ship>_
- Pre-flight verdict: _<ok:true; advisories>_
- Resulting pull-request link (then discarded): _<to record>_
- CI status at hand-back: _<green / no-required-checks carve-out>_
- Readout surfaced (yes/no): _<to record>_

> **Durable repeatable acceptance is #112.** This manual one-shot proves the live path once;
> turning it into a repeatable, recorded agentic check (re-runnable as a gate, not a one-time
> session) is tracked by [#112](https://github.com/zwrose/superheroes/issues/112).
