# Ledgers — bespoke-vs-platform and anti-opportunities

Two standing ledgers required by [PHILOSOPHY.md](PHILOSOPHY.md): **B6** (bespoke
machinery only where the platform lacks the primitive — every divergence is a named
decision with a re-check trigger) and **B7** (evidence before machinery — the things we
deliberately do not build are a first-class artifact, cited instead of re-litigated).

The **orientation review** (standing monthly-ish routine, deliberately independent of
the release path) walks both ledgers each pass: the first against the platform's current
primitives, the second against its own unlock conditions. Changes land by PR. An entry
nobody has re-checked in months is just drift with a paper trail.

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

## 3. Accepted residual risks

Known, owner-accepted gaps between a guarantee's prose and its enforcement — each with
its bound, why it was accepted, and the trigger that reopens it. Promise 5 applied to
ourselves: a residual risk we carry knowingly is a trade; one nobody wrote down is a
hidden defect. The orientation review walks this section too.

| Residual | Bound | Why accepted (owner-ratified) | Re-check trigger |
|---|---|---|---|
| **Worktree-confinement is a heuristic, not a sandbox — and engine subprocesses are not bound at all** (2026-07-09, #311/PR #335; amended 2026-07-15, #355). The enforcer's auto-allow parses command text for confined shapes, and its PreToolUse hook binds OUR agents' Bash — NOT a `--trust -f` external engine subprocess's children. The residual's re-check trigger FIRED in the wild (2026-07-10): a cursor fix leaf committed to the primary checkout's `main`, then self-reverted (no push, no damage this time). | The **post-dispatch confinement tripwire** (#355, `engine_dispatch.js`) now DETECTS an out-of-worktree engine write on the primary repo after every confined write dispatch — snapshotting HEAD reflog / HEAD sha / porcelain status before and after, where the **append-only reflog** catches a commit-and-self-revert excursion whose end state is clean — and emits a first-class `confinement_tripwire` journal event + a distinct narrator notice. It DETECTS, it does not prevent. Disclosed remaining blind spots (accepted): a direct `git push` mutates a remote and leaves the local probe clean; a write to a DIFFERENT on-disk repo, or a commit to a branch the primary has not checked out (only that branch's ref-log grows, not the primary HEAD reflog), is outside probed scope; a `.git`-internal write (planted hook / rewritten config) or a count-neutral working-tree edit (write-then-restore, or a further edit to an already-dirty file) moves none of the three signals; a within-window reflog gc/expiry could in principle mask count growth (very low probability); a detached child outliving the post-probe window escapes the sample; under concurrent runs sharing the primary checkout a breach receipt may mis-attribute the delta to the wrong engine/work-item (the reflog-only-grows property means concurrency never MASKS a real breach — attribution noise, not a missed detection). A timeout/threw dispatch whose CLI was never joined reports INDETERMINATE, not confined, and a breach whose durable receipt fails to persist is surfaced loudly on the live narrator line. | Detection-over-prevention is the honest bound today: physically sandboxing a `--trust` CLI is a shell sandbox the platform should own, and the ambient-credential push risk belongs to the enforcer/credential layer (#311/#335), not a per-dispatch probe. The tripwire converts a silent escape into an auditable receipt, so a real push / other-repo escape surfaces in review rather than transcript archaeology. | Claude Code ships a native process-sandboxing primitive that can confine a spawned CLI (walk with the enforcer's bespoke-vs-platform entry above); OR the tripwire observes a breach whose blast radius reached a REMOTE (a push) — that upgrades prevention from residual to defect (the local-only bound no longer holds) |
