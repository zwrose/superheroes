# Ledgers — bespoke-vs-platform and anti-opportunities

Two standing ledgers required by [PHILOSOPHY.md](PHILOSOPHY.md): **B6** (bespoke
machinery only where the platform lacks the primitive — every divergence is a named
decision with a re-check trigger) and **B7** (evidence before machinery — the things we
deliberately do not build are a first-class artifact, cited instead of re-litigated).

The **orientation review** (standing monthly-ish routine, deliberately independent of
the release path) walks both ledgers each pass: the first against the platform's current
primitives, the second against its own unlock conditions. Changes land by PR. An entry
nobody has re-checked in months is drift wearing a ledger costume.

## 1. Bespoke-vs-platform ledger

Every custom mechanism we maintain, the platform primitive that could absorb it, why we
still diverge, and the trigger that reopens the decision. Upstream requests are cited,
never duplicated — corroborate on the existing thread.

| Mechanism | What it is | Platform primitive that could absorb it | Why we still diverge | Re-check trigger |
|---|---|---|---|---|
| **Showrunner Workflow bundle** | The whole pipeline (build → review → ship) compiled into one Workflow-tool script (`lib/bundle_showrunner.js` emits it; smoke tests + a script-size cap guard it) | The Workflow tool itself, if scripts gained filesystem/exec access and first-class module composition | Workflow scripts today have no fs/exec and a hard script-size cap, so the spine must bundle its modules and delegate every side effect | Deterministic exec/fs lands upstream (requested: anthropics/claude-code#67684 + family) — re-check the bundle *and* the size-cap workarounds together |
| **Couriers** | Single-command Bash subagents the spine dispatches as dumb pipes for shell side effects (git, gh, store writes) | Direct exec from Workflow scripts (same upstream request) | The only way a Workflow script can touch the world today; conformance-tested, label-audited, `__badCourierAnswer` fenced | Same trigger as the bundle — couriers exist *only* because scripts cannot exec; they retire the day that ships |
| **Enforcer (PreToolUse hook)** | Deterministic guardrail layer: owner-authority floor (never merge/release/publish), worktree confinement, role-scoped command policy | Native permission rules (`settings.json` allow/deny/ask) | Native rules are static per-session and can't express per-role, per-worktree, or composed-command policy; the floor must hold *inside* spawned subagents too | Platform permission rules gain dynamic/role-scoped composition, or hooks gain a first-class policy API — walk the enforcer's rule inventory against it |
| **run_watch** | CLI watcher rendering a live run's `events.jsonl` into an owner-readable progress view | `/workflows` live progress UI + TaskOutput | The native view shows agent/phase structure but not our domain facts (gates, verdicts, park reasons, engine dispatches) in owner language | Native progress surfaces become extensible enough to carry domain rows — or the promise-6 read-back work (agent-as-interpreter) absorbs run_watch's job from the other side |

## 2. Anti-opportunities ledger

Owner-ratified negative space (2026-07-05 complexity-audit walkthrough, amended
2026-07-08/09). When tempted to propose any of these, the answer is no unless the
stated unlock condition is met — cite this ledger instead of re-arguing.

- **No sixth review seat.** #184's decision framework requires escape/recall evidence
  first; the remediation order is rubric amendment → seat swap → sixth seat.
- **No traceability reviewer built on spec.** Parked behind #184 + a named consumer;
  #230's conditional-dispatch seam makes it cheap IF evidence ever calls. *(The #33
  investigation itself unlocked 2026-07-09 — the false merge-ready escape + the terminal
  intent-gap audit — and folded into the spec-fidelity instrument's discovery, still not
  a new seat.)*
- **No per-phase engine matrices.** The engine surface is the highest external-drift
  burden per feature; it grows only if cross-vendor diversity demonstrably catches
  findings Claude misses (#131 measures — meaningful only once external review
  genuinely dispatches).
- **No general diff-aware round-1 roster routing.** #184 holds it; #230's narrow
  shape-trigger is the single sanctioned exception.
- **No calendar-based eval cadences.** Release-tied triggers (#237) superseded them;
  don't re-add "monthly runs." *(Scoped exception, owner-ratified 2026-07-08: the
  **orientation review** runs on a standing monthly-ish cadence, deliberately OFF the
  release path — a hotfix must never drag a research sweep into its critical path. The
  ban still fully covers calendar-based release evals and instrument runs.)*
- **No issue-level status tables in committed docs.** *(Reshaped, owner-ratified
  2026-07-09: [ROADMAP.md](ROADMAP.md) DOES carry the release train — cut rules,
  bundles, claims owed, build lane — updated at train-level events only, per CLAUDE.md's
  rule. The ban still covers issue-level status in committed docs, and the mechanics
  inventory stays a re-derived artifact, never committed.)*
- **No new honesty/grounding gates without a named escape that penetrated every
  existing layer.** The four verification layers (CI/parity, review evals, acceptance
  live-runs, release gate) absorb incidents within existing structure. *(This bar was
  met once: the 2026-07-08 engine-fidelity escape penetrated all four — the resulting
  investment is the 0.12–0.13 truth-telling train, not a fifth standing layer.)*
- **No storage-mode machinery investment.** Status quo decided 2026-07-05;
  `mode_migrate` demotion re-checks only inside the superpowers-severance pass (#111).
  Store-dir naming legibility (#137) is a different layer — allowed as a read-only
  mapping view, not dir renames.
- **No config knobs that keep both implementation variants alive** (e.g. fix-in-loop
  on/off) — pick once, deliberately. *(An owner-declared degradation **policy** is
  calibration — an owner trade under promise 5 — not an implementation hedge; that
  distinction was ruled in its issue, not here.)*
- **Backlog/TPM hero (#27–#31) + queue controller (#22).** Hold behind demonstrated
  multi-item queue pain; evaluate the pair together when it arrives.
- **Nothing already shipped gets rebuilt** because a session forgot it exists — check
  the store, the CHANGELOG, and the Project first.

**Unlock rhythm:** the stability gate (two consecutive releases whose first real runs
diagnose clean) re-opens the growth posture; #184's checkpoint re-opens
panel-composition; a real four-layer escape re-opens gate questions (spent once, see
above).
